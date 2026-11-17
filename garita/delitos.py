"""
Denuncias por comision de delitos por departamento (INEI, con datos del SIDPOL de la PNP).

El INEI publica en su indice tematico de Delitos dos Excel por departamento: el numero
de denuncias y la tasa por cada 10 mil habitantes, con el ultimo ano completo (2024).
No hay una serie oficial por provincia descargable; por eso el mapa combina el delito a
nivel de region con lo que si existe por provincia (sedes de empresas, estados de
emergencia y casos de la Defensoria).

**Lima.** El INEI separa "Lima Metropolitana" y "Region Lima". Se suman las denuncias y
la tasa se toma de su fila combinada ("Lima Metropolitana y Region Lima"), que el mismo
archivo publica.
"""

from __future__ import annotations

import logging

import pandas as pd

from .config import Config, configurar_logging, load_config
from .datos import normalizar
from .red import Cliente

log = logging.getLogger("garita.delitos")

BASE = "https://m.inei.gob.pe/media/MenuRecursivo/indices_tematicos/"
ARCHIVOS = {"denuncias": "2.%20Denuncias%20por%20comision%20de%20delitos%20%20-%20Dpto_1_1.xlsx",
            "tasa": "3.%20Tasa%20de%20denuncias%20por%20comision%20de%20delitos%20-%20Dpto_1_1.xlsx"}
PAGINA = "https://www.inei.gob.pe/estadisticas/indice-tematico/crimes/"


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.14 Descarga: los dos Excel del indice tematico de Delitos del INEI
def descargar(cfg: Config) -> dict[str, "Path"]:
    cli = Cliente(cfg)
    rutas = {}
    for clave, archivo in ARCHIVOS.items():
        destino = cfg.raw_dir / "inei" / f"{clave}_dpto.xlsx"
        cli.descargar(BASE + archivo, destino)
        rutas[clave] = destino
    return rutas


# --- 03.15 Lectura: detecta la fila de anos y toma la ultima columna con datos
def _leer(ruta) -> tuple[pd.Series, int]:
    x = pd.read_excel(ruta, header=None)
    fila_anios = x.index[x.iloc[:, 0].astype(str).str.strip() == "Departamento"][0]
    anios = pd.to_numeric(x.iloc[fila_anios, 1:], errors="coerce")
    col = anios.last_valid_index()
    anio = int(anios[col])
    datos = x.iloc[fila_anios + 1:, [0, col]].dropna()
    datos.columns = ["nombre", "valor"]
    datos["nombre"] = datos["nombre"].astype(str).str.replace(r"\s*\d/", "", regex=True).str.strip()
    return datos.set_index("nombre")["valor"].astype(float), anio


# --- 03.16 Limpieza y salida: departamentos canonicos, Lima sumada, ranking
def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    log = configurar_logging("garita.delitos")
    rutas = descargar(cfg)
    den, anio = _leer(rutas["denuncias"])
    tasa, anio_t = _leer(rutas["tasa"])
    filas = []
    for nombre, valor in den.items():
        n = normalizar(nombre)
        if n in ("TOTAL", "LIMA METROPOLITANA", "REGION LIMA", "LIMA METROPOLITANA Y LIMA",
                 "LIMA METROPOLITANA Y REGION LIMA") or n.startswith(("NOTA", "FUENTE")):
            continue
        dep = "CALLAO" if "CALLAO" in n else n
        filas.append({"departamento": dep, "denuncias": int(valor),
                      "tasa_10mil": round(float(tasa.get(nombre, float("nan"))), 1)})
    lima_den = sum(int(v) for k, v in den.items() if normalizar(k) in ("LIMA METROPOLITANA", "REGION LIMA"))
    lima_tasa = next((v for k, v in tasa.items() if normalizar(k).startswith("LIMA METROPOLITANA Y")), None)
    filas.append({"departamento": "LIMA", "denuncias": lima_den,
                  "tasa_10mil": round(float(lima_tasa), 1) if lima_tasa else None})
    df = pd.DataFrame(filas).drop_duplicates("departamento")
    df["anio"] = anio
    df["ranking_tasa"] = df["tasa_10mil"].rank(ascending=False, method="min").astype(int)
    df["fuente"] = PAGINA
    df.to_parquet(cfg.processed_dir / "delitos_departamento.parquet", index=False)
    resumen = {"fecha_corte": pd.Timestamp.today().date().isoformat(), "anio": anio,
               "departamentos": int(len(df)), "denuncias_total": int(df["denuncias"].sum()), "url": PAGINA}
    log.info("Delitos listo: %s", resumen)
    return resumen


if __name__ == "__main__":
    ejecutar()
