"""
Registro de costos de cada llamada al LLM y tope de gasto.

Adaptado de HW3_Diaz/tarea1_rag_normativo/src/costos.py: misma tabla (fecha, modelo,
franja tarifaria, tokens, latencia, costo en USD, exito o error) y misma regla de
precios por franja horaria de DeepSeek. Se registran tambien las llamadas fallidas: una
tabla que solo cuenta los exitos miente sobre lo que costo llegar al resultado.

Lo nuevo es el **tope**: antes de cada llamada se suma lo gastado y, si se alcanzo
GARITA_TOPE_USD, se lanza TopeAlcanzado. La app lo atrapa y sigue en modo demo.
"""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import Config, load_config

COLUMNAS = ["timestamp_utc", "tarea", "modelo", "franja", "tokens_entrada",
            "tokens_entrada_cache_hit", "tokens_salida", "latencia_seg", "costo_usd",
            "exito", "error"]

_CANDADO = threading.Lock()


class TopeAlcanzado(RuntimeError):
    """Se alcanzo el tope de gasto en LLM."""


@dataclass
class Llamada:
    timestamp_utc: str
    tarea: str
    modelo: str
    franja: str
    tokens_entrada: int
    tokens_entrada_cache_hit: int
    tokens_salida: int
    latencia_seg: float
    costo_usd: float
    exito: bool
    error: str = ""


# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.6 Costos: tokens, latencia y dolares de cada llamada, con tope de gasto
class RegistroCostos:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        self.ruta: Path = self.cfg.root / self.cfg.costos["archivo_log"]
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        if not self.ruta.exists():
            with open(self.ruta, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(COLUMNAS)

    def calcular(self, entrada: int, cache_hit: int, salida: int,
                 momento: datetime) -> tuple[str, float]:
        franja, p = self.cfg.tarifa_vigente(momento)
        miss = max(entrada - cache_hit, 0)
        costo = (cache_hit / 1e6 * p["entrada_cache_hit"] + miss / 1e6 * p["entrada_cache_miss"]
                 + salida / 1e6 * p["salida"])
        return franja, costo

    def registrar(self, *, tarea: str, modelo: str, entrada: int, salida: int,
                  latencia: float, cache_hit: int = 0, exito: bool = True,
                  error: str = "") -> Llamada:
        momento = datetime.now(timezone.utc)
        franja, costo = self.calcular(entrada, cache_hit, salida, momento)
        ll = Llamada(momento.isoformat(timespec="seconds"), tarea, modelo, franja, entrada,
                     cache_hit, salida, round(latencia, 3), round(costo, 8), exito, error[:200])
        with _CANDADO, open(self.ruta, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([asdict(ll)[c] for c in COLUMNAS])
        return ll

    def total_usd(self) -> float:
        if not self.ruta.exists():
            return 0.0
        df = pd.read_csv(self.ruta)
        return float(df["costo_usd"].sum()) if len(df) else 0.0

    def verificar_tope(self) -> None:
        tope = self.cfg.tope_usd()
        gastado = self.total_usd()
        if gastado >= tope:
            raise TopeAlcanzado(f"Se alcanzo el tope de US${tope:.2f} (gastado US${gastado:.4f}).")

    def resumen(self) -> pd.DataFrame:
        if not self.ruta.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.ruta)
        if df.empty:
            return df
        g = df.groupby("tarea")
        return pd.DataFrame({
            "llamadas": g.size(),
            "exitosas": g["exito"].sum(),
            "tokens_entrada_prom": g["tokens_entrada"].mean().round(0),
            "tokens_salida_prom": g["tokens_salida"].mean().round(0),
            "latencia_mediana_seg": g["latencia_seg"].median().round(2),
            "costo_usd_total": g["costo_usd"].sum().round(5),
            "costo_usd_por_llamada": g["costo_usd"].mean().round(6),
        }).reset_index()
