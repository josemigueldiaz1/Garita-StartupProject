"""
Configuracion unica del proyecto: rutas, parametros de config.yaml y secretos.

**Los secretos nunca se imprimen.** `credencial()` devuelve el valor o None, y
`estado_credenciales()` solo dice si la clave esta cargada. Ningun log, ninguna
pagina de la app y ningun commit muestran su valor.

**Orden de busqueda de la clave:** primero el `.env` de la raiz del repo (local),
despues `st.secrets` (Streamlit Community Cloud). Si no aparece en ninguno, la app
sigue en modo demo con los datos ya procesados.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, time as dtime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


class Config:
    """Envoltura de config.yaml con accesos por seccion y rutas ya resueltas."""

    def __init__(self, datos: dict[str, Any]):
        self.d = datos
        self.root = RAIZ
        for clave, rel in datos["rutas"].items():
            ruta = RAIZ / rel
            ruta.mkdir(parents=True, exist_ok=True)
            setattr(self, f"{clave}_dir", ruta)

    def __getattr__(self, nombre: str) -> Any:
        try:
            return self.d[nombre]
        except KeyError as e:
            raise AttributeError(nombre) from e

    # ----------------------------------------------------------------- secretos
    @staticmethod
    def credencial(nombre: str) -> str | None:
        """Lee un secreto de .env o de st.secrets. Devuelve None si no existe."""
        valor = os.getenv(nombre)
        if valor:
            return valor.strip()
        try:
            import streamlit as st

            if nombre in st.secrets:
                return str(st.secrets[nombre]).strip()
        except Exception:  # noqa: BLE001 - fuera de Streamlit no hay st.secrets
            pass
        return None

    @staticmethod
    def estado_credenciales() -> dict[str, bool]:
        """Solo si la clave esta cargada o no. Nunca su valor."""
        return {"DEEPSEEK_API_KEY": bool(Config.credencial("DEEPSEEK_API_KEY"))}

    def tope_usd(self) -> float:
        valor = self.credencial("GARITA_TOPE_USD")
        try:
            return float(valor) if valor else float(self.llm["tope_usd_defecto"])
        except ValueError:
            return float(self.llm["tope_usd_defecto"])

    # ------------------------------------------------------------------ tarifas
    def tarifa_vigente(self, momento: datetime) -> tuple[str, dict[str, float]]:
        """
        Franja (pico o valle) y precios por millon de tokens en ese instante.

        DeepSeek cobra la mitad fuera de sus horas pico; el costo de una llamada es
        funcion del momento en que se hizo. Logica tomada de costos.py del HW3.
        """
        c = self.costos
        m = momento.astimezone(timezone.utc)
        es_habil = m.weekday() < 5
        en_pico = False
        if es_habil or not c.get("solo_dias_habiles", True):
            for f in c["horas_pico_utc"]:
                desde = dtime.fromisoformat(f["desde"])
                hasta = dtime.fromisoformat(f["hasta"])
                if desde <= m.time() < hasta:
                    en_pico = True
                    break
        franja = "pico" if en_pico else "valle"
        return franja, c["precios_por_millon"][franja]


@lru_cache(maxsize=1)
def load_config(ruta: str | None = None) -> Config:
    archivo = Path(ruta) if ruta else RAIZ / "config.yaml"
    with open(archivo, encoding="utf-8") as fh:
        return Config(yaml.safe_load(fh))


def configurar_logging(nombre: str, nivel: int = logging.INFO) -> logging.Logger:
    """Log a consola y a logs/<nombre>.log. Un proceso silencioso es un proceso roto."""
    cfg = load_config()
    log = logging.getLogger(nombre)
    if log.handlers:
        return log
    log.setLevel(nivel)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")
    consola = logging.StreamHandler()
    consola.setFormatter(fmt)
    log.addHandler(consola)
    archivo = logging.FileHandler(cfg.logs_dir / f"{nombre}.log", encoding="utf-8")
    archivo.setFormatter(fmt)
    log.addHandler(archivo)
    return log
