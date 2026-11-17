"""
Conflictos sociales por provincia desde el reporte mensual de la Defensoria del Pueblo.

El reporte es un PDF de ~140 paginas, sin datos abiertos tabulares. Cada caso viene
como un bloque con "Caso:", "Tipo:" y "Ubicacion: ... provincia de X, departamento de
Y". Se leen esos bloques con PyMuPDF y expresiones regulares; no hace falta OCR porque
el PDF tiene capa de texto.

**El nombre del archivo no es confiable.** El PDF publicado como "n-270" dice en su
encabezado "N.° 269 – AGOSTO 2026". Por eso el numero y el mes se leen del contenido.

**Que cuenta el mapa.** Casos distintos que el reporte ubica en cada provincia. Un
caso que abarca varias provincias suma en todas. Es una senal de riesgo social de la
zona, no un indice de criminalidad: se dice asi en la app.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from .config import Config, configurar_logging, load_config
from .datos import normalizar
from .red import Cliente, decodificar

log = logging.getLogger("garita.defensoria")

DEPARTAMENTOS = ["AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA",
                 "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD",
                 "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA",
                 "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI"]


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.13 Descarga: el reporte mas reciente desde el indice de la Defensoria
def ultimo_reporte(cfg: Config, cli: Cliente) -> tuple[str, "Path"]:
    html = decodificar(cli.get(cfg.defensoria["indice"]))
    links = set(re.findall(r'href="([^"]+\.pdf)"', html))
    candidatos = []
    for u in links:
        m = re.search(cfg.defensoria["patron_pdf"] + r"", u)
        n = re.search(r"-n-(\d+)", u, re.I)
        if m and n:
            candidatos.append((int(n.group(1)), u))
    if not candidatos:
        raise RuntimeError("No se encontro ningun reporte de conflictos en el indice.")
    _, url = max(candidatos)
    destino = cfg.raw_dir / "defensoria" / url.rsplit("/", 1)[-1]
    cli.descargar(url, destino)
    return url, destino


# ===== HERRAMIENTA 10 · Document AI =====
# --- 10.5 Lectura: bloques de caso del PDF con su tipo y su ubicacion
def leer_casos(pdf_path, provincias_validas: set[tuple[str, str]]) -> tuple[dict, pd.DataFrame]:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    paginas = [p.get_text() for p in doc]
    cab = re.search(r"N\.?\s*°\s*(\d+)\s*[–-]\s*([A-ZÁÉÍÓÚ]+)\s+(\d{4})", paginas[2] if len(paginas) > 2 else "")
    meta = {"reporte": f"N.° {cab.group(1)}" if cab else "", "mes": f"{cab.group(2).title()} {cab.group(3)}" if cab else ""}

    prov_por_nombre: dict[str, list[str]] = {}
    for dep, prov in provincias_validas:
        prov_por_nombre.setdefault(prov, []).append(dep)

    casos = []
    for i, texto in enumerate(paginas, start=1):
        for bloque in re.split(r"(?=Caso\s*:)", texto)[1:]:
            b = " ".join(bloque[:2500].split())
            nombre = re.match(r"Caso\s*:\s*(.{5,160}?)(?: Descripci| Tipo| Fecha| Ubicaci|$)", b)
            tipo = re.search(r"Tipo\s*:\s*([A-Za-zÁÉÍÓÚáéíóúñÑ/ ]{3,60}?)(?: Ubicaci| Estado| Fecha| Actores| Solicitante|$)", b)
            provs = re.findall(r"[Pp]rovincias? de ([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñÑ ]{2,40}?)(?=,|\.| y | departamento| región| regi| distrito|\)|$)", b)
            deps = re.findall(r"(?:departamento|regi[oó]n) (?:de )?([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñÑ ]{2,25}?)(?=,|\.|\)| y |$| Estado| Tipo| Actores)", b)
            dep_ok = [normalizar(d) for d in deps if normalizar(d) in DEPARTAMENTOS]
            for p in provs:
                pn = normalizar(p)
                candidatos = prov_por_nombre.get(pn, [])
                if not candidatos:
                    continue
                dep = next((d for d in dep_ok if d in candidatos), candidatos[0])
                casos.append({"caso": nombre.group(1).strip() if nombre else b[6:90],
                              "tipo": tipo.group(1).strip() if tipo else "",
                              "departamento": dep, "provincia": pn, "pagina": i})
    df = pd.DataFrame(casos).drop_duplicates(subset=["caso", "provincia"]) if casos else pd.DataFrame(
        columns=["caso", "tipo", "departamento", "provincia", "pagina"])
    df["socioambiental"] = df["tipo"].str.contains("ocioambiental", case=False, na=False)
    return meta, df


# --- 10.6 Lectura: cuadros oficiales por region y por actividad
def leer_cuadros(pdf_path) -> tuple[pd.DataFrame, dict]:
    """
    Cuadro N.° 3 (conflictos por estado, segun region) y N.° 15 (socioambientales por
    actividad). El formato 2026 del reporte ya no lista los 188 casos con su ubicacion;
    el conteo oficial por departamento solo esta en el Cuadro 3. Lima Metropolitana y
    Lima Provincias se suman en LIMA.
    """
    import pymupdf

    texto = "\n".join(p.get_text() for p in pymupdf.open(pdf_path))
    plano = " ".join(texto.split())
    c3 = re.search(r"CONFLICTOS SOCIALES POR ESTADO, SEG[ÚU]N REGI[ÓO]N(.{0,2500}?)(?:Fuente|Cuadro)", plano)
    filas = []
    if c3:
        for nombre, total, activo, latente in re.findall(
                r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-Za-záéíóúñ]+){0,3}) (\d+) [\d.]+% (\d+|-) (\d+|-)", c3.group(1)):
            dep = normalizar(nombre)
            dep = "LIMA" if dep.startswith("LIMA") else dep
            if dep in DEPARTAMENTOS:
                filas.append({"departamento": dep, "conflictos": int(total),
                              "activos": int(activo) if activo != "-" else 0,
                              "latentes": int(latente) if latente != "-" else 0})
    deps = (pd.DataFrame(filas).groupby("departamento", as_index=False).sum()
            if filas else pd.DataFrame(columns=["departamento", "conflictos", "activos", "latentes"]))
    extra = {}
    total = re.search(r"CONFLICTOS SOCIALES, SEG[ÚU]N TIPO.{0,80}?TOTAL (\d+)", plano)
    socio = re.search(r"CONFLICTOS SOCIOAMBIENTALES, SEG[ÚU]N ACTIVIDAD.{0,80}?TOTAL (\d+) [\d.]+% Miner[íi]a (\d+)", plano)
    if total:
        extra["conflictos_total"] = int(total.group(1))
    if socio:
        extra["socioambientales"] = int(socio.group(1))
        extra["socioambientales_mineria"] = int(socio.group(2))
    return deps, extra


# --- 10.7 Salida: conflictos.parquet, conflictos_provincia y conflictos_departamento
def ejecutar(cfg: Config | None = None) -> dict:
    import geopandas as gpd

    cfg = cfg or load_config()
    log = configurar_logging("garita.defensoria")
    cli = Cliente(cfg)
    url, pdf = ultimo_reporte(cfg, cli)
    prov = gpd.read_file(cfg.processed_dir / "provincias_base.geojson")
    validas = set(zip(prov["departamento"], prov["provincia"]))
    meta, casos = leer_casos(pdf, validas)
    casos["reporte"], casos["mes"] = meta["reporte"], meta["mes"]
    casos["estado"] = ""
    casos.to_parquet(cfg.processed_dir / "conflictos.parquet", index=False)
    cp = (casos.groupby(["departamento", "provincia"])
               .agg(n_casos=("caso", "nunique"),
                    n_socioambientales=("socioambiental", "sum"))
               .reset_index())
    cp["n_activos"] = 0
    cp.to_parquet(cfg.processed_dir / "conflictos_provincia.parquet", index=False)
    deps, extra = leer_cuadros(pdf)
    deps.to_parquet(cfg.processed_dir / "conflictos_departamento.parquet", index=False)
    resumen = {"url": url, **meta, **extra, "casos_ubicados": int(len(casos)),
               "provincias_con_casos": int(len(cp)), "departamentos_cuadro3": int(len(deps)),
               "suma_cuadro3": int(deps["conflictos"].sum()) if len(deps) else 0}
    log.info("Defensoria lista: %s", resumen)
    return resumen
