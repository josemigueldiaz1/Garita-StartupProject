"""
Acceso a los datos procesados. La app, el servidor MCP y la skill leen de aqui.

Ninguna de las tres interfaces abre un parquet por su cuenta: si cambia una columna,
se arregla en un solo lugar. Todo sale de data/processed, que esta versionado en el
repo, asi que estas funciones nunca llaman a internet ni al LLM. Ese es el modo demo:
si se cae una fuente o falta la clave, la app sigue respondiendo con lo ya procesado.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from functools import lru_cache

import pandas as pd

from .config import load_config


def normalizar(texto: str | None) -> str:
    """Mayusculas y sin tildes: la forma canonica de departamentos y provincias."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    t = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


@lru_cache(maxsize=32)
def tabla(nombre: str) -> pd.DataFrame:
    """Lee data/processed/<nombre>.parquet. Devuelve un DataFrame vacio si no existe."""
    ruta = load_config().processed_dir / f"{nombre}.parquet"
    if not ruta.exists():
        return pd.DataFrame()
    return pd.read_parquet(ruta)


def metadatos() -> dict:
    ruta = load_config().processed_dir / "metadatos.json"
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def limpiar_cache() -> None:
    tabla.cache_clear()


# ------------------------------------------------------------------- empresas
def buscar_empresas(departamento: str, modalidad: str = "VIGILANCIA PRIVADA",
                    armas: str | None = None, provincia: str | None = None,
                    solo_vigentes: bool = True) -> pd.DataFrame:
    """
    Empresas con sede autorizada por SUCAMEC en un departamento y modalidad.

    `armas`: "CON ARMAS" exige autorizacion de vigilancia con armas; "SIN ARMAS" o
    None aceptan cualquiera. Devuelve una fila por RUC con sus sedes en el
    departamento, la provincia de la sede (si coincide con la pedida se marca) y la
    autorizacion vigente que vence antes.
    """
    r = tabla("sucamec_resoluciones")
    if r.empty:
        return r
    m = r["departamento"] == normalizar(departamento)
    if modalidad:
        m &= r["modalidad"] == normalizar(modalidad)
    if solo_vigentes:
        m &= r["vigente"]
    if armas and normalizar(armas) == "CON ARMAS":
        m &= r["armas"] == "CON ARMAS"
    sel = r[m].copy()
    if sel.empty:
        return sel
    prov = normalizar(provincia) if provincia else None
    sel["sede_en_provincia"] = sel["provincia"] == prov if prov else False
    agg = (sel.sort_values("fecha_vencimiento")
              .groupby("ruc")
              .agg(razon_social=("razon_social", "first"),
                   resoluciones=("resolucion", lambda s: " | ".join(sorted(set(s)))),
                   armas=("armas", lambda s: "CON ARMAS" if "CON ARMAS" in set(s) else s.iloc[0]),
                   vencimiento=("fecha_vencimiento", "min"),
                   provincias_sede=("provincia", lambda s: " | ".join(sorted(set(s)))),
                   sede_en_provincia=("sede_en_provincia", "max"),
                   direccion=("direccion", "first"))
              .reset_index())
    agg["departamento"] = normalizar(departamento)
    agg["modalidad"] = normalizar(modalidad)
    return agg


def modalidades_de(ruc: str, solo_vigentes: bool = True) -> pd.DataFrame:
    """Todas las autorizaciones de un RUC: sirve para verificar CCTV, GPS o accesos."""
    r = tabla("sucamec_resoluciones")
    if r.empty:
        return r
    sel = r[r["ruc"] == str(ruc)]
    if solo_vigentes:
        sel = sel[sel["vigente"]]
    return sel.sort_values(["modalidad", "departamento"])


def ficha_empresa(ruc: str) -> dict:
    """Todo lo que Garita sabe de un RUC, por fuente. Las claves faltantes son None."""
    ruc = str(ruc)

    def fila(nombre: str) -> dict | None:
        t = tabla(nombre)
        if t.empty or "ruc" not in t:
            return None
        f = t[t["ruc"] == ruc]
        return None if f.empty else f.iloc[0].to_dict()

    auts = modalidades_de(ruc)
    return {
        "ruc": ruc,
        "empresa": fila("empresas"),
        "autorizaciones": auts.to_dict("records") if not auts.empty else [],
        "sunat": fila("sunat_ruc"),
        "oece": fila("proveedores_oece"),
        "experiencia_publica": fila("experiencia_publica"),
    }


# ------------------------------------------------------------------ contratos
def contratos_vigilancia(departamento: str | None = None, solo_validos: bool = True,
                         ruc_proveedor: str | None = None) -> pd.DataFrame:
    """Contratos publicos de vigilancia con su precio por puesto-mes ya normalizado."""
    b = tabla("benchmark_contratos")
    if b.empty:
        return b
    m = pd.Series(True, index=b.index)
    if departamento:
        m &= b["departamento"] == normalizar(departamento)
    if solo_validos and "valido" in b:
        m &= b["valido"]
    if ruc_proveedor:
        m &= b["ruc_proveedor"] == str(ruc_proveedor)
    return b[m].sort_values("fecha_firma", ascending=False)


def benchmark(departamento: str | None = None) -> dict:
    """
    Rango de precio por puesto 24/7 y mes en un departamento.

    Si el departamento tiene menos de 3 contratos validos se devuelve el nacional y
    se avisa en `alcance`: un percentil sobre dos contratos no describe un mercado.
    """
    b = tabla("benchmark_departamento")
    if b.empty:
        return {}
    dep = normalizar(departamento) if departamento else "PERU"
    f = b[b["departamento"] == dep]
    if f.empty or int(f.iloc[0]["n"]) < 3:
        nac = b[b["departamento"] == "PERU"]
        if nac.empty:
            return {}
        d = nac.iloc[0].to_dict()
        d["alcance"] = "nacional"
        d["motivo"] = (f"{dep.title()} tiene menos de 3 contratos validos; se usa el rango nacional."
                       if dep != "PERU" else "")
        return d
    d = f.iloc[0].to_dict()
    d["alcance"] = "departamental"
    return d


# ---------------------------------------------------------------------- riesgo
def estados_emergencia(departamento: str | None = None, provincia: str | None = None) -> pd.DataFrame:
    """Estados de emergencia vigentes (tabla curada a mano con su decreto, data/manual)."""
    ruta = load_config().root / "data" / "manual" / "estados_emergencia.csv"
    if not ruta.exists():
        return pd.DataFrame()
    e = pd.read_csv(ruta, dtype=str).fillna("")
    e["fecha_fin"] = pd.to_datetime(e["fecha_fin"], errors="coerce")
    e = e[e["fecha_fin"].isna() | (e["fecha_fin"] >= pd.Timestamp(hoy()))]
    if departamento:
        e = e[e["departamento"].map(normalizar) == normalizar(departamento)]
    if provincia:
        e = e[(e["provincia"].map(normalizar) == normalizar(provincia)) | (e["provincia"] == "")]
    return e


def riesgo_zona(departamento: str, provincia: str | None = None) -> dict:
    """
    Tres senales de riesgo de la zona, cada una con su fuente:

    - Conflictos sociales del departamento (Cuadro 3 del reporte de la Defensoria):
      el conteo oficial, con activos y latentes, y su puesto entre los 25.
    - Casos que el reporte ubica en la provincia (secciones de alertas, mediacion y
      acuerdos): el reporte 2026 ya no lista todos los casos, asi que es un minimo.
    - Estados de emergencia vigentes por decreto supremo (tabla curada).
    """
    dep = normalizar(departamento)
    prov = normalizar(provincia) if provincia else None
    meta = metadatos().get("defensoria", {})
    out: dict = {"departamento": dep, "provincia": prov, "reporte": meta.get("reporte"),
                 "mes": meta.get("mes"), "fuente": meta.get("url")}
    cd = tabla("conflictos_departamento")
    if not cd.empty:
        f = cd[cd["departamento"] == dep]
        if not f.empty:
            out.update({"conflictos_departamento": int(f.iloc[0]["conflictos"]),
                        "activos_departamento": int(f.iloc[0]["activos"]),
                        "latentes_departamento": int(f.iloc[0]["latentes"])})
        out["ranking_departamento"] = int(cd.set_index("departamento")["conflictos"]
                                          .rank(ascending=False, method="min").get(dep, 0))
    cp = tabla("conflictos_provincia")
    if prov and not cp.empty:
        p = cp[(cp["departamento"] == dep) & (cp["provincia"] == prov)]
        out["casos_provincia"] = int(p["n_casos"].sum()) if not p.empty else 0
    casos = tabla("conflictos")
    if not casos.empty:
        c = casos[casos["departamento"] == dep]
        if prov:
            c = c[c["provincia"] == prov]
        out["casos"] = c[["caso", "tipo", "provincia", "pagina"]].head(10).to_dict("records")
    em = estados_emergencia(dep, prov)
    out["estados_emergencia"] = em.assign(fecha_fin=em["fecha_fin"].dt.strftime("%Y-%m-%d")).to_dict(
        "records") if not em.empty else []
    return out


def hoy() -> date:
    return date.today()
