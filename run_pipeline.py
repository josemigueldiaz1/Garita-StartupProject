"""
Pipeline de Garita: descarga, lee, normaliza y deja data/processed lista para la app.

    uv run python run_pipeline.py                         # todo menos el LLM
    uv run python run_pipeline.py --pasos extraer,benchmark   # gasta tokens (con tope)
    uv run python run_pipeline.py --pasos sucamec --forzar

Cada paso es re-ejecutable: lo ya descargado o ya extraido no se vuelve a pedir (salvo
--forzar). El paso `extraer` es el unico que llama al LLM y respeta GARITA_TOPE_USD.

| Paso        | Herramienta del curso | Que hace                                              |
|-------------|-----------------------|-------------------------------------------------------|
| sucamec     | 03 Scraping y APIs    | registro de empresas autorizadas (formulario JSF)     |
| oece        | 03 Scraping y APIs    | contratos de vigilancia de 12 meses (API OCDS)        |
| sunat       | 03 Scraping y APIs    | estado y condicion del RUC (padron reducido)          |
| proveedores | 03 Scraping y APIs    | ficha OECE: inhabilitacion, penalidades, sanciones    |
| geo         | 06 GeoPandas y Folium | provincias disueltas desde distritos y centroides     |
| defensoria  | 03 + 10 Document AI   | conflictos por region y provincia desde el PDF        |
| delitos     | 03 Scraping y APIs    | denuncias por departamento (INEI, SIDPOL de la PNP)    |
| documentos  | 10 Document AI        | Bases: triaje, OCR solo en paginas imagen, TDR        |
| extraer     | 08 LLM estructurado   | puestos, horas, armado y perfil en JSON + Pydantic    |
| benchmark   | 08 (calculo Python)   | precio por puesto-mes y rango por departamento        |
| metadatos   | —                     | fechas de corte y conteos para la app                 |
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import date

import pandas as pd

from garita.config import configurar_logging, load_config

PASOS = ["sucamec", "oece", "sunat", "proveedores", "geo", "defensoria", "delitos", "documentos",
         "extraer", "benchmark", "metadatos"]
POR_DEFECTO = [p for p in PASOS if p != "extraer"]


def paso_proveedores(cfg) -> dict:
    from garita.oece import fichas

    p = cfg.processed_dir
    rucs = list(pd.read_parquet(p / "empresas.parquet")["ruc"])
    rucs += list(pd.read_parquet(p / "contratos_vigilancia.parquet")["ruc_proveedor"].dropna())
    f = fichas(rucs, cfg)
    return {"fichas": int(len(f)), "en_registro": int(f["en_registro"].sum()),
            "no_aptos": int((f["apto_contratar"] == False).sum()),  # noqa: E712
            "con_penalidades": int((f["n_penalidades"] > 0).sum())}


def paso_geo(cfg) -> dict:
    from garita import geo

    r = geo.construir_capas(cfg)
    geo.unir_conflictos(cfg)
    return r


def paso_defensoria(cfg) -> dict:
    from garita import defensoria, geo

    r = defensoria.ejecutar(cfg)
    geo.unir_conflictos(cfg)
    return r


def metadatos(cfg, resultados: dict) -> dict:
    """Fecha de corte y conteos por fuente. Conserva lo que no se re-ejecuto."""
    ruta = cfg.processed_dir / "metadatos.json"
    meta = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    hoy = date.today().isoformat()
    nombres = {"sucamec": "sucamec", "oece": "oece", "sunat": "sunat",
               "proveedores": "proveedores_oece", "defensoria": "defensoria", "delitos": "delitos",
               "documentos": "documentos", "extraer": "extraccion_llm", "benchmark": "benchmark"}
    for paso, r in resultados.items():
        if paso in nombres and isinstance(r, dict):
            meta[nombres[paso]] = {"fecha_corte": hoy, **r}
    ruta.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--pasos", default=",".join(POR_DEFECTO),
                    help=f"pasos separados por coma: {', '.join(PASOS)}")
    ap.add_argument("--forzar", action="store_true",
                    help="borra la cache del paso (descargas o extracciones) y lo rehace")
    a = ap.parse_args()
    pasos = [p.strip() for p in a.pasos.split(",") if p.strip()]
    desconocidos = set(pasos) - set(PASOS)
    if desconocidos:
        ap.error(f"pasos desconocidos: {', '.join(sorted(desconocidos))}")

    cfg = load_config()
    log = configurar_logging("garita.pipeline")
    if a.forzar:
        cache = {"oece": cfg.raw_dir / "oece", "sunat": cfg.raw_dir / "sunat",
                 "documentos": cfg.processed_dir / "tdr_textos.parquet",
                 "extraer": cfg.processed_dir / "extracciones_llm.parquet",
                 "proveedores": cfg.processed_dir / "proveedores_oece.parquet"}
        for p in pasos:
            ruta = cache.get(p)
            if ruta and ruta.exists():
                shutil.rmtree(ruta) if ruta.is_dir() else ruta.unlink()
                log.info("--forzar: borrado %s", ruta)

    from garita import benchmark, delitos, documentos, extraccion, oece, sucamec, sunat

    funciones = {"sucamec": sucamec.ejecutar, "oece": oece.ejecutar, "sunat": sunat.ejecutar,
                 "proveedores": paso_proveedores, "geo": paso_geo, "defensoria": paso_defensoria,
                 "delitos": delitos.ejecutar,
                 "documentos": documentos.ejecutar, "extraer": extraccion.ejecutar,
                 "benchmark": benchmark.construir}
    resultados = {}
    for p in [x for x in PASOS if x in pasos and x != "metadatos"]:
        t0 = time.perf_counter()
        log.info("=== paso %s", p)
        resultados[p] = funciones[p](cfg)
        log.info("=== paso %s listo en %.0fs", p, time.perf_counter() - t0)
    if "metadatos" in pasos or resultados:
        metadatos(cfg, resultados)


if __name__ == "__main__":
    main()
