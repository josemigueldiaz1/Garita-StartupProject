"""
Estado y condicion del RUC desde el padron reducido de SUNAT.

La consulta RUC web de SUNAT responde 403 a peticiones automatizadas y pide captcha.
SUNAT publica el mismo dato completo como padron reducido: un ZIP de ~395 MB con un
TXT separado por "|" (RUC, razon social, estado, condicion de domicilio, ubigeo y
direccion). Se descarga una vez, se recorre linea por linea sin cargarlo entero en
memoria y se guardan solo los RUC de empresas de seguridad y de ganadores de
contratos de vigilancia.

**Solo personas juridicas (RUC 20).** El padron incluye a personas naturales con
negocio (RUC 10, que contienen el DNI). Garita no las guarda.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date

import pandas as pd

from .config import Config, configurar_logging, load_config
from .red import Cliente

log = logging.getLogger("garita.sunat")


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.10 Descarga: padron reducido del RUC (archivo publico de SUNAT)
def descargar_padron(cfg: Config) -> "Path":
    destino = cfg.raw_dir / "sunat" / "padron_reducido_ruc.zip"
    Cliente(cfg).descargar(cfg.sunat["padron_url"], destino)
    log.info("  padron: %.0f MB", destino.stat().st_size / 1e6)
    return destino


# --- 03.11 Lectura y limpieza: filtra los RUC de interes linea por linea
def filtrar_padron(zip_path, rucs: set[str]) -> pd.DataFrame:
    rucs = {r for r in rucs if r and r.startswith("20")}
    filas = []
    with zipfile.ZipFile(zip_path) as zf:
        nombre = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        with zf.open(nombre) as fh:
            texto = io.TextIOWrapper(fh, encoding="latin-1", errors="replace")
            next(texto)  # cabecera
            for linea in texto:
                ruc = linea[:11]
                if ruc in rucs:
                    c = linea.rstrip("\n").split("|")
                    filas.append({"ruc": c[0], "razon_social_sunat": c[1].strip(),
                                  "estado": c[2].strip(), "condicion": c[3].strip(),
                                  "ubigeo": c[4].strip()})
    return pd.DataFrame(filas)


# --- 03.12 Salida: data/processed/sunat_ruc.parquet
def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    log = configurar_logging("garita.sunat")
    p = cfg.processed_dir
    rucs = set(pd.read_parquet(p / "empresas.parquet")["ruc"])
    contratos = pd.read_parquet(p / "contratos_vigilancia.parquet")
    rucs |= set(contratos["ruc_proveedor"].dropna())
    log.info("SUNAT: %d RUC de interes", len(rucs))
    z = descargar_padron(cfg)
    df = filtrar_padron(z, rucs)
    df["fecha_padron"] = pd.Timestamp(date.fromtimestamp(z.stat().st_mtime))
    df.to_parquet(p / "sunat_ruc.parquet", index=False)
    resumen = {"rucs_buscados": len(rucs), "encontrados": int(len(df)),
               "activos_habidos": int(((df["estado"] == "ACTIVO") & (df["condicion"] == "HABIDO")).sum())}
    log.info("SUNAT listo: %s", resumen)
    return resumen


if __name__ == "__main__":
    ejecutar()
