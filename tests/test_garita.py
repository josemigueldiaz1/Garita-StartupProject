"""Pruebas de la logica de Garita que no dependen de internet ni de la clave del LLM."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from garita import benchmark
from garita.esquemas import ExtraccionTDR
from garita.extraccion import _fila_extraccion
from garita.llm import ClienteLLM
from garita.pedido import documento_por_reglas, interpretar_por_reglas


# ===== HERRAMIENTA 12 · Despliegue y evaluacion =====
# --- 12.4 Pruebas: cliente falso del LLM, conversion de puestos y respaldos sin LLM
class _RespuestaFalsa:
    def __init__(self, contenido: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=contenido))]
        self.usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=200, prompt_tokens_details=None)


class _ApiFalsa:
    """Devuelve primero un JSON invalido y luego uno valido: ejercita el reintento."""

    def __init__(self, respuestas: list[str]):
        self.respuestas = list(respuestas)
        self.mensajes_recibidos = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kw):
        self.mensajes_recibidos.append(kw["messages"])
        assert kw["response_format"] == {"type": "json_object"}
        return _RespuestaFalsa(self.respuestas.pop(0))


VALIDO = {"puede_extraer": True, "puestos": [
    {"descripcion": "Puerta principal", "cantidad": 2, "horas_por_dia": 24, "dias_por_semana": 7, "armado": True},
    {"descripcion": "Almacen", "cantidad": 1, "horas_por_dia": 12, "dias_por_semana": 7, "armado": True}],
    "plazo_meses": 12, "confianza": "alta", "evidencia": "02 puestos de 24 horas y 01 de 12 horas"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    c = ClienteLLM()
    c.costos.ruta = tmp_path / "costos.csv"
    c.costos.ruta.write_text("timestamp_utc,tarea,modelo,franja,tokens_entrada,tokens_entrada_cache_hit,"
                             "tokens_salida,latencia_seg,costo_usd,exito,error\n", encoding="utf-8")
    return c


def test_reintenta_si_el_json_no_valida(cliente):
    malo = json.dumps({"puede_extraer": True, "puestos": [{"cantidad": -3, "horas_por_dia": 24}]})
    api = _ApiFalsa([malo, json.dumps(VALIDO)])
    cliente._cliente = api
    obj, uso = cliente.estructurado("sistema", "usuario", ExtraccionTDR, tarea="prueba")
    assert uso["intentos"] == 2
    assert "no cumple el esquema" in api.mensajes_recibidos[1][-1]["content"]
    assert len(obj.puestos) == 2
    assert cliente.costos.total_usd() > 0


def test_dos_fallos_no_inventan_datos(cliente):
    cliente._cliente = _ApiFalsa(["no es json", "{}"])
    with pytest.raises(RuntimeError):
        cliente.estructurado("s", "u", ExtraccionTDR, tarea="prueba")


def test_conversion_a_puestos_equivalentes():
    fila = SimpleNamespace(ocid="ocds-prueba")
    out = _fila_extraccion(fila, ExtraccionTDR.model_validate(VALIDO), {"costo_usd": 0.001}, "")
    assert out["n_puestos_24h"] == 2 and out["n_puestos_12h"] == 1
    assert out["puestos_equivalentes_24h"] == pytest.approx(2.5)
    assert out["armado"] == "si"


def test_piso_legal_con_rmv_vigente():
    piso24 = benchmark.costo_laboral_minimo(24)
    piso12 = benchmark.costo_laboral_minimo(12)
    assert piso24.supuestos["rmv"] == 1230
    assert piso24.piso_puesto_mes > piso12.piso_puesto_mes > 0
    assert 3.5 < piso24.agentes_necesarios < 4.0


def test_precio_puesto_mes():
    assert benchmark.precio_puesto_mes(960000, 8, 12) == 10000
    assert benchmark.precio_puesto_mes(960000, 0, 12) is None


def test_pedido_por_reglas():
    r = interpretar_por_reglas("vigilancia con armas, 8 puestos 24/7, campamento minero en Pataz, La Libertad, 12 meses")
    assert r["n_puestos"] == 8 and r["horas_por_dia"] == 24 and r["con_armas"] is True
    assert r["plazo_meses"] == 12 and r["tipo_sitio"] == "campamento"
    assert r.get("provincia") in (None, "PATAZ")


def test_documento_por_reglas():
    r = documento_por_reglas("CARTA FIANZA por S/ 96,000.00 vigente desde el 15/11/2026 hasta el 14/02/2027")
    assert r["tipo_documento"] == "carta_fianza" and r["monto"] == 96000
    assert r["fecha_vencimiento"] == "2027-02-14"
