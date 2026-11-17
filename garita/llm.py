"""
Cliente del LLM: DeepSeek (deepseek-chat) con salida JSON validada por Pydantic.

DeepSeek no tiene SDK propio: se usa el cliente de OpenAI con
base_url="https://api.deepseek.com", igual que en el HW3. La clave se lee de
DEEPSEEK_API_KEY (.env en local, Secrets en Streamlit Cloud) y nunca se imprime.

Tres decisiones que conviene saber defender:

1. **JSON + Pydantic, no prosa.** Se pide `response_format={"type": "json_object"}` y
   la respuesta se valida contra un esquema de esquemas.py. Los numeros llegan como
   numeros; ningun regex interpreta el texto del modelo.
2. **Un reintento con el error.** Si el JSON no valida, se le devuelve al modelo el
   mensaje de Pydantic una sola vez. Si vuelve a fallar, se registra el error y el
   proceso queda fuera del benchmark: un hueco es mejor que un dato inventado.
3. **Sin clave o sin presupuesto, modo demo.** `disponible()` dice si hay clave y
   saldo; la app la consulta antes de ofrecer cualquier funcion que llame al modelo.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import Config, load_config
from .costos import RegistroCostos, TopeAlcanzado

log = logging.getLogger("garita.llm")
T = TypeVar("T", bound=BaseModel)


class SinClave(RuntimeError):
    """No hay DEEPSEEK_API_KEY: la app sigue en modo demo."""


# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.4 Cliente: DeepSeek con el SDK de OpenAI, JSON y validacion Pydantic
class ClienteLLM:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        self.p = self.cfg.llm
        self.costos = RegistroCostos(self.cfg)
        self._cliente = None

    def disponible(self) -> tuple[bool, str]:
        if not Config.credencial("DEEPSEEK_API_KEY"):
            return False, "Falta la clave de DeepSeek: la app usa los datos ya procesados."
        try:
            self.costos.verificar_tope()
        except TopeAlcanzado as e:
            return False, str(e)
        return True, ""

    def _api(self):
        if self._cliente is None:
            clave = Config.credencial("DEEPSEEK_API_KEY")
            if not clave:
                raise SinClave("Falta DEEPSEEK_API_KEY.")
            from openai import OpenAI

            self._cliente = OpenAI(api_key=clave, base_url=self.p["base_url"])
        return self._cliente

    def estructurado(self, sistema: str, usuario: str, esquema: type[T],
                     tarea: str) -> tuple[T, dict]:
        """
        Una llamada que devuelve un objeto del `esquema` ya validado y el uso de tokens.

        Lanza SinClave, TopeAlcanzado o RuntimeError (API o validacion); quien llama
        decide si eso detiene el lote o solo marca la fila.
        """
        self.costos.verificar_tope()
        mensajes = [{"role": "system", "content": sistema},
                    {"role": "user", "content": usuario}]
        uso = {"tokens_entrada": 0, "tokens_salida": 0, "costo_usd": 0.0, "intentos": 0}
        ultimo_error = ""
        for intento in (1, 2):
            uso["intentos"] = intento
            t0 = time.perf_counter()
            try:
                r = self._api().chat.completions.create(
                    model=self.p["modelo"], messages=mensajes,
                    temperature=float(self.p["temperatura"]),
                    max_tokens=int(self.p["max_tokens"]),
                    timeout=float(self.p["timeout_seg"]),
                    response_format={"type": "json_object"},
                )
            except SinClave:
                raise
            except Exception as e:  # noqa: BLE001 - error de red o de la API
                self.costos.registrar(tarea=tarea, modelo=self.p["modelo"], entrada=0,
                                      salida=0, latencia=time.perf_counter() - t0,
                                      exito=False, error=f"{type(e).__name__}: {e}")
                raise RuntimeError(f"La API fallo: {type(e).__name__}: {str(e)[:160]}") from e

            u = r.usage
            detalles = getattr(u, "prompt_tokens_details", None)
            cache_hit = int(getattr(detalles, "cached_tokens", 0) or 0) if detalles else 0
            crudo = (r.choices[0].message.content or "").strip()
            try:
                obj = esquema.model_validate(json.loads(crudo))
                ll = self.costos.registrar(tarea=tarea, modelo=self.p["modelo"],
                                           entrada=u.prompt_tokens, salida=u.completion_tokens,
                                           cache_hit=cache_hit,
                                           latencia=time.perf_counter() - t0)
                uso["tokens_entrada"] += u.prompt_tokens
                uso["tokens_salida"] += u.completion_tokens
                uso["costo_usd"] += ll.costo_usd
                return obj, uso
            except (json.JSONDecodeError, ValidationError) as e:
                ultimo_error = str(e)[:600]
                ll = self.costos.registrar(tarea=tarea, modelo=self.p["modelo"],
                                           entrada=u.prompt_tokens, salida=u.completion_tokens,
                                           cache_hit=cache_hit,
                                           latencia=time.perf_counter() - t0,
                                           exito=False, error="validacion: " + ultimo_error)
                uso["tokens_entrada"] += u.prompt_tokens
                uso["tokens_salida"] += u.completion_tokens
                uso["costo_usd"] += ll.costo_usd
                mensajes += [{"role": "assistant", "content": crudo},
                             {"role": "user", "content":
                              "Tu JSON no cumple el esquema. Error de validacion:\n"
                              f"{ultimo_error}\nDevuelve el JSON corregido, solo el JSON."}]
        raise RuntimeError(f"El JSON no valido tras 2 intentos: {ultimo_error[:200]}")


_CLIENTE: ClienteLLM | None = None


def cliente() -> ClienteLLM:
    global _CLIENTE
    if _CLIENTE is None:
        _CLIENTE = ClienteLLM()
    return _CLIENTE
