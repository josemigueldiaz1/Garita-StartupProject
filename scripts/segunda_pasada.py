"""
Segunda pasada sobre las Bases que no dieron puestos en la primera lectura.

    uv run python scripts/segunda_pasada.py

1. Relee con la regla nueva (re-OCR de paginas clave, ZIP y Bases escaneadas) solo los
   procesos que fallaron o en los que el LLM no encontro puestos.
2. Vuelve a extraer esos procesos con el LLM (respeta el tope de gasto).
3. Reconstruye el benchmark, corre la evaluacion y actualiza metadatos.json.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from garita import benchmark, documentos, extraccion  # noqa: E402
from garita.config import configurar_logging, load_config  # noqa: E402
from run_pipeline import metadatos  # noqa: E402


def main() -> None:
    cfg = load_config()
    log = configurar_logging("garita.segunda_pasada")
    p = cfg.processed_dir
    ext = pd.read_parquet(p / "extracciones_llm.parquet")
    txt = pd.read_parquet(p / "tdr_textos.parquet")
    fallidos = set(ext.loc[~ext["puede_extraer"].fillna(False).astype(bool), "ocid"])
    fallidos |= set(txt.loc[(txt["error"].fillna("") != "") | (txt["caracteres"] < 3000), "ocid"])
    log.info("Segunda pasada: %d procesos a releer", len(fallidos))
    r_doc = documentos.ejecutar(cfg, releer=fallidos)
    r_ext = extraccion.ejecutar(cfg, reintentar_sin_puestos=True)
    r_bm = benchmark.construir(cfg)
    log.info("benchmark: %s", r_bm)
    metadatos(cfg, {"documentos": r_doc, "extraer": r_ext, "benchmark": r_bm})
    subprocess.run([sys.executable, str(RAIZ / "eval" / "evaluar_extraccion.py")], check=False)


if __name__ == "__main__":
    main()
