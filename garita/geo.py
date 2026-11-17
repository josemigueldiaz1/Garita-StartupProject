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


# --- 06.3 Mapa: coropletico de conflictos por provincia con el sitio y las sedes
def mapa_riesgo(departamento: str, provincia: str | None = None,
                sedes: pd.DataFrame | None = None):
    """
    Mapa Folium del departamento: provincias coloreadas por casos registrados por la
    Defensoria, la provincia del cliente resaltada y las sedes de las empresas de la
    lista corta como marcadores.
    """
    import folium
    import geopandas as gpd

    cfg = load_config()
    ruta = cfg.processed_dir / "provincias.geojson"
    if not ruta.exists():
        return None
    gdf = gpd.read_file(ruta)
    dep = normalizar(departamento)
    sub = gdf[gdf["departamento"] == dep]
    if sub.empty:
        return None
    # Centro y zoom explicitos: st_folium ignora fit_bounds y mostraba el planisferio.
    b = sub.total_bounds
    lado = max(b[2] - b[0], b[3] - b[1])
    zoom = 8 if lado < 2 else 7 if lado < 4 else 6
    m = folium.Map(location=[(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], zoom_start=zoom,
                   tiles="OpenStreetMap", control_scale=True)
    # Escala secuencial de un solo tono (azul claro -> oscuro) para la magnitud; el
    # rojo queda reservado para alertas. 0 casos = gris neutro, no "poco azul".
    rampa = {0: "#f0efec", 1: "#9ec5f4", 2: "#5598e7", 3: "#1c5cab"}

    def estilo(f):
        n = int(f["properties"]["n_casos"])
        es_cliente = provincia and f["properties"]["provincia"] == normalizar(provincia)
        return {"fillColor": rampa[min(n, 3)], "fillOpacity": 0.75,
                "color": "#0b0b0b" if es_cliente else "#898781",
                "weight": 3 if es_cliente else 0.6}

    folium.GeoJson(
        sub.to_json(), style_function=estilo,
        tooltip=folium.GeoJsonTooltip(
            fields=["provincia", "n_casos", "n_socioambientales"],
            aliases=["Provincia", "Conflictos registrados", "Socioambientales"]),
    ).add_to(m)
    if provincia:
        c = centroide(dep, provincia)
        if c:
            folium.Marker(c, tooltip=f"Sitio del cliente: {provincia.title()}",
                          icon=folium.Icon(color="black", icon="star")).add_to(m)
    if sedes is not None and not sedes.empty:
        for s in sedes.itertuples():
            if pd.notna(getattr(s, "lat", None)):
                folium.CircleMarker((s.lat, s.lon), radius=6, color="#ffffff", weight=2,
                                    fill=True, fill_color="#eb6834", fill_opacity=0.95,
                                    tooltip=f"{s.razon_social} · sede en {str(s.provincia).title()}"
                                    ).add_to(m)
    return m
