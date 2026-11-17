"""
Limites provinciales y mapas: GeoPandas para construir la capa, Folium para mostrarla.

La sesion 06 del curso trae limites departamentales y distritales, pero no
provinciales. Las provincias se construyen disolviendo los 1,834 distritos por
(departamento, provincia) con GeoPandas: la union de los distritos de una provincia
es la provincia. Se simplifica la geometria para que el GeoJSON pese poco y el mapa
cargue rapido en Streamlit Cloud.

Los centroides de cada distrito sirven ademas para ubicar las sedes de las empresas
(SUCAMEC publica el ubigeo de cada sede) y medir su distancia al sitio del cliente.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

from .config import Config, configurar_logging, load_config
from .datos import normalizar

log = logging.getLogger("garita.geo")


# ===== HERRAMIENTA 06 · GeoPandas y Folium =====
# --- 06.1 Capa: disuelve distritos en provincias y guarda centroides
def construir_capas(cfg: Config | None = None) -> dict:
    import geopandas as gpd

    cfg = cfg or load_config()
    configurar_logging("garita.geo")
    dist = gpd.read_file(cfg.geo["distrital_url"])
    dist["departamento"] = dist["NOMBDEP"].map(normalizar)
    dist["provincia"] = dist["NOMBPROV"].map(normalizar)
    dist["distrito"] = dist["NOMBDIST"].map(normalizar)

    prov = dist.dissolve(by=["departamento", "provincia"], as_index=False)[
        ["departamento", "provincia", "geometry"]]
    prov["geometry"] = prov.geometry.simplify(0.01, preserve_topology=True)
    prov.to_file(cfg.processed_dir / "provincias_base.geojson", driver="GeoJSON")

    # Centroides en una proyeccion metrica (UTM 18S) y de vuelta a grados.
    cent = dist.to_crs(32718).centroid.to_crs(4326)
    puntos = pd.DataFrame({"departamento": dist["departamento"], "provincia": dist["provincia"],
                           "distrito": dist["distrito"], "lat": cent.y, "lon": cent.x})
    puntos.to_parquet(cfg.processed_dir / "centroides_distritos.parquet", index=False)
    log.info("Capas: %d provincias, %d distritos", len(prov), len(puntos))
    return {"provincias": int(len(prov)), "distritos": int(len(puntos))}


# --- 06.2 Union: conflictos por provincia sobre la capa de provincias
def unir_conflictos(cfg: Config | None = None) -> None:
    import geopandas as gpd

    cfg = cfg or load_config()
    prov = gpd.read_file(cfg.processed_dir / "provincias_base.geojson")
    cp_ruta = cfg.processed_dir / "conflictos_provincia.parquet"
    cp = pd.read_parquet(cp_ruta) if cp_ruta.exists() else pd.DataFrame(
        columns=["departamento", "provincia", "n_casos", "n_socioambientales", "n_activos"])
    out = prov.merge(cp, on=["departamento", "provincia"], how="left")
    for c in ("n_casos", "n_socioambientales", "n_activos"):
        out[c] = out[c].fillna(0).astype(int)
    out.to_file(cfg.processed_dir / "provincias.geojson", driver="GeoJSON")


@lru_cache(maxsize=1)
def capa_provincias():
    """Provincias con sus casos de la Defensoria. Se lee una vez por proceso."""
    import geopandas as gpd

    return gpd.read_file(load_config().processed_dir / "provincias.geojson")


@lru_cache(maxsize=1)
def capa_departamentos():
    """Departamentos disueltos desde las provincias, con delitos, conflictos y empresas."""
    from .datos import ranking_regiones

    prov = capa_provincias()
    dep = prov.dissolve(by="departamento", as_index=False)[["departamento", "geometry"]]
    dep["geometry"] = dep.geometry.simplify(0.02, preserve_topology=True)
    return dep.merge(ranking_regiones(), on="departamento", how="left")


# Icono de Font Awesome segun el motivo del estado de emergencia
def _icono_emergencia(motivo: str) -> str:
    m = normalizar(motivo)
    if "MINERIA" in m:
        return "diamond"
    if "NARCO" in m or "DROGA" in m:
        return "leaf"
    if "CRIMIN" in m or "DELITO" in m or "EXTORSION" in m or "VIOLENCIA" in m:
        return "crosshairs"
    return "exclamation-triangle"


CAPAS = {"Tasa de delitos (por 10 mil hab.)": ("tasa_10mil", "Denuncias por 10 mil hab. (INEI 2024)"),
         "Conflictos sociales": ("conflictos", "Conflictos sociales (Defensoria)"),
         "Empresas autorizadas": ("empresas_vigilancia", "Empresas con autorizacion de vigilancia")}


# --- 06.3 Mapa nacional: regiones coloreadas, region elegida, emergencias, conflictos y empresas
def mapa_region(departamento: str, provincia: str | None = None, capa: str = "Tasa de delitos (por 10 mil hab.)",
                empresas_por_provincia: pd.DataFrame | None = None):
    """
    Peru completo coloreado por la capa elegida, centrado en la region seleccionada.

    - Regiones: escala secuencial de un tono (azul) en cinco tramos por cuantiles.
    - Region elegida: borde negro y sus provincias dibujadas encima.
    - Burbujas naranjas: empresas con sede autorizada en cada provincia de la region.
    - Iconos rojos: estados de emergencia vigentes en todo el pais (rombo = mineria
      ilegal, mira = crimen organizado, hoja = narcotrafico).
    - Iconos de fuego: provincias con casos en el reporte de la Defensoria.
    - Estrella: el sitio del cliente.
    """
    import folium

    from .datos import estados_emergencia

    deps = capa_departamentos()
    prov = capa_provincias()
    dep = normalizar(departamento)
    col, nombre_capa = CAPAS.get(capa, next(iter(CAPAS.values())))
    sub = prov[prov["departamento"] == dep]
    b = sub.total_bounds if not sub.empty else deps.total_bounds
    lado = max(b[2] - b[0], b[3] - b[1])
    zoom = 8 if lado < 2 else 7 if lado < 4 else 6
    m = folium.Map(location=[(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], zoom_start=zoom,
                   tiles="OpenStreetMap", control_scale=True)

    valores = deps[col].fillna(0)
    cortes = sorted(set(valores.quantile([0.2, 0.4, 0.6, 0.8]).round(1)))
    rampa = ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"]

    def color(v):
        return rampa[sum(v > c for c in cortes)] if pd.notna(v) else "#f0efec"

    def estilo(f):
        p = f["properties"]
        elegida = p["departamento"] == dep
        return {"fillColor": color(p.get(col)), "fillOpacity": 0.55 if not elegida else 0.35,
                "color": "#0b0b0b" if elegida else "#ffffff", "weight": 3 if elegida else 1}

    campos = ["departamento", "tasa_10mil", "denuncias", "conflictos", "emergencias", "empresas_vigilancia"]
    folium.GeoJson(
        deps[campos + ["geometry"]].to_json(), style_function=estilo,
        tooltip=folium.GeoJsonTooltip(fields=campos, aliases=[
            "Region", "Delitos por 10 mil hab. (2024)", "Denuncias (2024)", "Conflictos sociales",
            "Estados de emergencia", "Empresas autorizadas"]),
        name="Regiones").add_to(m)

    if not sub.empty:
        folium.GeoJson(
            sub[["provincia", "n_casos", "geometry"]].to_json(),
            style_function=lambda f: {"fillOpacity": 0, "color": "#52514e", "weight": 0.8,
                                      "dashArray": "3"},
            tooltip=folium.GeoJsonTooltip(fields=["provincia", "n_casos"],
                                          aliases=["Provincia", "Casos (Defensoria)"]),
            name="Provincias").add_to(m)
        for r in sub[sub["n_casos"] > 0].itertuples():
            c = centroide(dep, r.provincia)
            if c:
                folium.Marker(c, tooltip=f"{r.provincia.title()}: {r.n_casos} caso(s) en el reporte de la Defensoria",
                              icon=folium.Icon(color="orange", icon="fire", prefix="fa")).add_to(m)

    if empresas_por_provincia is not None and not empresas_por_provincia.empty:
        for r in empresas_por_provincia.itertuples():
            c = centroide(dep, r.provincia)
            if c and r.empresas > 0:
                folium.CircleMarker(c, radius=5 + 2.2 * (r.empresas ** 0.5), color="#ffffff", weight=2,
                                    fill=True, fill_color="#eb6834", fill_opacity=0.9,
                                    tooltip=f"{r.provincia.title()}: {r.empresas} empresas con sede autorizada "
                                            f"({r.con_armas} con armas)").add_to(m)

    em = estados_emergencia()
    for r in em.itertuples():
        c = centroide(r.departamento, r.provincia or None)
        if c:
            hasta = f"hasta {pd.Timestamp(r.fecha_fin):%d/%m/%Y}" if pd.notna(r.fecha_fin) else "vigencia por confirmar"
            folium.Marker(c, tooltip=f"Estado de emergencia · {str(r.provincia or r.departamento).title()} · "
                                     f"{r.norma} · {hasta}",
                          popup=folium.Popup(str(r.motivo)[:300], max_width=320),
                          icon=folium.Icon(color="red", icon=_icono_emergencia(r.motivo), prefix="fa")).add_to(m)

    if provincia:
        c = centroide(dep, provincia)
        if c:
            folium.Marker(c, tooltip=f"Sitio del cliente: {provincia.title()}",
                          icon=folium.Icon(color="black", icon="star", prefix="fa")).add_to(m)
    return m, nombre_capa


def centroide(departamento: str, provincia: str | None = None,
              distrito: str | None = None) -> tuple[float, float] | None:
    """Lat/lon del distrito, o el promedio de la provincia o del departamento."""
    from .datos import tabla

    c = tabla("centroides_distritos")
    if c.empty:
        return None
    m = c["departamento"] == normalizar(departamento)
    if provincia:
        m &= c["provincia"] == normalizar(provincia)
    if distrito:
        m2 = m & (c["distrito"] == normalizar(distrito))
        if m2.any():
            m = m2
    sel = c[m]
    if sel.empty:
        return None
    return float(sel["lat"].mean()), float(sel["lon"].mean())


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distancia en linea recta (haversine). Por carretera suele ser 1.3 a 2 veces mas."""
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))
