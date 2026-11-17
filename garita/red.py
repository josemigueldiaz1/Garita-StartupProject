"""
Cliente HTTP compartido por los scrapers: pausa entre peticiones y reintentos.

Mismo patron que ClienteOECE del HW3. La pausa es una cortesia con servicios
publicos gratuitos y evita un bloqueo temporal que costaria mas tiempo del que se
ahorra. Cada respuesta fallida se reintenta con espera creciente; si todas fallan se
lanza un error con la URL, nunca se devuelve una respuesta vacia como si fuera valida.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from .config import Config, load_config

log = logging.getLogger("garita.red")


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.0 Cliente HTTP: pausa entre peticiones, reintentos y descarga atomica
class Cliente:
    def __init__(self, cfg: Config | None = None, espera: float | None = None):
        cfg = cfg or load_config()
        r = cfg.red
        self.espera = float(espera if espera is not None else r["segundos_entre_peticiones"])
        self.timeout = int(r["timeout_seg"])
        self.reintentos = int(r["reintentos"])
        self.ses = requests.Session()
        self.ses.headers.update({"User-Agent": r["user_agent"]})
        self.n_peticiones = 0
        self._ultima = 0.0

    def _throttle(self) -> None:
        dt = time.perf_counter() - self._ultima
        if dt < self.espera:
            time.sleep(self.espera - dt)
        self._ultima = time.perf_counter()

    def pedir(self, metodo: str, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", self.timeout)
        ultimo: Exception | None = None
        for intento in range(1, self.reintentos + 1):
            self._throttle()
            try:
                r = self.ses.request(metodo, url, **kw)
                self.n_peticiones += 1
                r.raise_for_status()
                return r
            except Exception as e:  # noqa: BLE001
                ultimo = e
                log.warning("  peticion fallida (%d/%d) %s: %s", intento, self.reintentos,
                            url[:80], str(e)[:120])
                time.sleep(2 * intento)
        raise RuntimeError(f"No se pudo obtener {url} tras {self.reintentos} intentos: {ultimo}")

    def get(self, url: str, **kw) -> requests.Response:
        return self.pedir("GET", url, **kw)

    def post(self, url: str, **kw) -> requests.Response:
        return self.pedir("POST", url, **kw)

    def descargar(self, url: str, destino: Path, forzar: bool = False) -> Path:
        """
        Descarga a disco por bloques. Re-ejecutable: si el archivo ya existe no se pide.

        Se escribe a un temporal y se renombra al final: un corte nunca deja un archivo
        truncado que la siguiente corrida daria por bueno.
        """
        if destino.exists() and destino.stat().st_size > 0 and not forzar:
            return destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        r = self.pedir("GET", url, stream=True)
        tmp = destino.with_suffix(destino.suffix + ".parcial")
        with open(tmp, "wb") as fh:
            for bloque in r.iter_content(1 << 20):
                fh.write(bloque)
        tmp.replace(destino)
        return destino


def decodificar(r: requests.Response) -> str:
    """
    Texto de la respuesta con la codificacion correcta.

    SUCAMEC declara UTF-8 pero algunas filas llegan en Windows-1252 (las tildes salen
    como caracter de reemplazo). Se intenta UTF-8 estricto y, si falla, cp1252.
    """
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("cp1252", errors="replace")
