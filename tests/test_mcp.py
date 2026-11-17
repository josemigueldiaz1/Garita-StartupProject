"""
El contrato del servidor MCP de Garita y de las cuentas de garita/benchmark.py.

    uv run pytest tests/test_mcp.py

Las tablas de prueba son sinteticas y diminutas (RUC inventados que empiezan con 2099):
las pruebas pasan aunque data/processed este vacio, y no dependen de lo que traiga la
descarga del dia. Se reemplaza `garita.datos.tabla` con monkeypatch, asi que se prueba
el mismo camino que usan la app y el servidor.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

from garita import benchmark as bm  # noqa: E402
from garita import datos  # noqa: E402
from mcp_server import server  # noqa: E402

HOY = date.today()
FUTURO = pd.Timestamp(HOY.replace(year=HOY.year + 2))
PASADO = pd.Timestamp(HOY.replace(year=HOY.year - 1))


# ===== HERRAMIENTA 04 · MCP =====
# --- 04.7 Pruebas: tablas sinteticas con la forma de docs/datos.md
def _tablas() -> dict[str, pd.DataFrame]:
    sucamec = pd.DataFrame([
        # armada, con sede en Pataz
        dict(ruc="20990000001", razon_social="ANDES PROTECCION S.A.C.", resolucion="001-2026",
             fecha_vencimiento=FUTURO, vigente=True, sede="SUCURSAL", direccion="JR. UNO 100",
             departamento="LA LIBERTAD", provincia="PATAZ", distrito="PATAZ",
             modalidad="VIGILANCIA PRIVADA", modalidad_texto="SERVICIO DE VIGILANCIA PRIVADA",
             armas="CON ARMAS", fecha_consulta=pd.Timestamp(HOY)),
        # sin armas, sede en Trujillo
        dict(ruc="20990000002", razon_social="COSTA VIGILANCIA S.R.L.", resolucion="002-2026",
             fecha_vencimiento=FUTURO, vigente=True, sede="PRINCIPAL", direccion="AV. DOS 200",
             departamento="LA LIBERTAD", provincia="TRUJILLO", distrito="TRUJILLO",
             modalidad="VIGILANCIA PRIVADA", modalidad_texto="SERVICIO DE VIGILANCIA PRIVADA - SIN ARMAS",
             armas="SIN ARMAS", fecha_consulta=pd.Timestamp(HOY)),
        # vencida: nunca debe aparecer como autorizada
        dict(ruc="20990000003", razon_social="VENCIDA S.A.", resolucion="003-2020",
             fecha_vencimiento=PASADO, vigente=False, sede="PRINCIPAL", direccion="CALLE TRES 300",
             departamento="LA LIBERTAD", provincia="TRUJILLO", distrito="TRUJILLO",
             modalidad="VIGILANCIA PRIVADA", modalidad_texto="SERVICIO DE VIGILANCIA PRIVADA",
             armas="CON ARMAS", fecha_consulta=pd.Timestamp(HOY)),
        # la empresa armada tambien tiene video a distancia
        dict(ruc="20990000001", razon_social="ANDES PROTECCION S.A.C.", resolucion="004-2026",
             fecha_vencimiento=FUTURO, vigente=True, sede="PRINCIPAL", direccion="JR. UNO 100",
             departamento="LA LIBERTAD", provincia="TRUJILLO", distrito="TRUJILLO",
             modalidad="TECNOLOGIA - VIDEO A DISTANCIA", modalidad_texto="VIDEO A DISTANCIA",
             armas="NO APLICA", fecha_consulta=pd.Timestamp(HOY)),
    ])
    empresas = pd.DataFrame([dict(ruc="20990000001", razon_social="ANDES PROTECCION S.A.C.",
                                  n_resoluciones=2, n_departamentos=1, departamentos="LA LIBERTAD",
                                  modalidades="TECNOLOGIA - VIDEO A DISTANCIA|VIGILANCIA PRIVADA",
                                  vigilancia_con_armas=True, vencimiento_proximo=FUTURO)])
    sunat = pd.DataFrame([dict(ruc="20990000001", estado="ACTIVO", condicion="HABIDO",
                               ubigeo="130801", fecha_padron=pd.Timestamp(HOY))])
    oece = pd.DataFrame([dict(ruc="20990000001", apto_contratar=True, habilitado=True,
                              n_penalidades=0, n_sanciones=float("nan"),
                              actualizado_al=pd.Timestamp(HOY), url_ficha="https://ejemplo")])
    contratos = pd.DataFrame([
        dict(ocid=f"ocds-prueba-{i}", entidad="ENTIDAD", departamento="LA LIBERTAD",
             proveedor="ANDES PROTECCION S.A.C.", ruc_proveedor="20990000001",
             monto_contrato=120000.0 * (i + 1), fecha_firma=pd.Timestamp(2026, 6, i + 1),
             duracion_dias=365, meses=12.0, n_puestos_24h=1, n_puestos_12h=0,
             puestos_equivalentes_24h=1.0, armado="si", precio_puesto_mes=10000.0 * (i + 1),
             confianza="alta", evidencia="01 puesto de 24 horas", url_bases="https://ejemplo",
             valido=True)
        for i in range(5)
    ])
    bench = pd.DataFrame([
        dict(departamento="PERU", n=40, p25=9000.0, mediana=10500.0, p75=12500.0, minimo=7000.0, maximo=20000.0),
        dict(departamento="LA LIBERTAD", n=5, p25=9500.0, mediana=11000.0, p75=13000.0, minimo=8000.0, maximo=15000.0),
        dict(departamento="CAJAMARCA", n=1, p25=9900.0, mediana=9900.0, p75=9900.0, minimo=9900.0, maximo=9900.0),
    ])
    conflictos_prov = pd.DataFrame([
        dict(departamento="LA LIBERTAD", provincia="PATAZ", n_casos=4, n_socioambientales=3, n_activos=4),
        dict(departamento="LA LIBERTAD", provincia="TRUJILLO", n_casos=1, n_socioambientales=0, n_activos=1),
        dict(departamento="LORETO", provincia="MAYNAS", n_casos=9, n_socioambientales=7, n_activos=8),
    ])
    casos = pd.DataFrame([dict(reporte="N.° 269", mes="2026-08", caso="Caso de prueba", tipo="Socioambiental",
                               estado="Activo", departamento="LA LIBERTAD", provincia="PATAZ",
                               distrito="PATAZ", pagina=40)])
    conflictos_dep = pd.DataFrame([
        dict(departamento="LA LIBERTAD", conflictos=5, activos=4, latentes=1),
        dict(departamento="LORETO", conflictos=18, activos=12, latentes=6),
    ])
    return {"sucamec_resoluciones": sucamec, "empresas": empresas, "sunat_ruc": sunat,
            "proveedores_oece": oece, "benchmark_contratos": contratos,
            "benchmark_departamento": bench, "conflictos_provincia": conflictos_prov,
            "conflictos": casos, "conflictos_departamento": conflictos_dep}


@pytest.fixture
def datos_falsos(monkeypatch):
    tablas = _tablas()
    monkeypatch.setattr(datos, "tabla", lambda nombre: tablas.get(nombre, pd.DataFrame()))
    monkeypatch.setattr(datos, "metadatos", lambda: {"defensoria": {"reporte": "N.° 269"}})
    return tablas


@pytest.fixture
def sin_datos(monkeypatch):
    monkeypatch.setattr(datos, "tabla", lambda nombre: pd.DataFrame())
    monkeypatch.setattr(datos, "metadatos", lambda: {})


# --------------------------------------------------------------- el servidor
def test_registra_las_ocho_herramientas_de_solo_lectura():
    herramientas = asyncio.run(server.mcp.list_tools())
    nombres = {t.name for t in herramientas}
    assert nombres == {"buscar_empresas", "ficha_empresa", "contratos_vigilancia", "benchmark_precio",
                       "costo_laboral_minimo", "evaluar_oferta", "riesgo_zona", "puntaje_confianza"}
    # El SDK v2 de MCP renombro readOnlyHint a read_only_hint; se acepta cualquiera.
    solo_lectura = [getattr(t.annotations, "read_only_hint", None) for t in herramientas]
    if None in solo_lectura:
        solo_lectura = [t.annotations.readOnlyHint for t in herramientas]
    assert all(solo_lectura)


def test_sin_pipeline_responde_con_error_claro(sin_datos):
    with pytest.raises(ToolError, match="run_pipeline"):
        server.buscar_empresas("La Libertad")
    with pytest.raises(ToolError, match="run_pipeline"):
        server.riesgo_zona("La Libertad")


def test_buscar_empresas_solo_vigentes_y_armadas(datos_falsos):
    r = server.buscar_empresas("la libertad", armas="con armas", provincia="Pataz")
    rucs = [e["ruc"] for e in r["empresas"]]
    assert rucs == ["20990000001"]           # la vencida y la sin armas quedan fuera
    assert r["empresas"][0]["sede_en_provincia"] is True
    assert r["nivel"] == "verificado" and r["fuente"].startswith("https://www.sucamec.gob.pe")
    json.dumps(r)                            # serializable: fechas ISO, sin NaN


def test_buscar_empresas_sin_filtro_de_armas_trae_ambas(datos_falsos):
    r = server.buscar_empresas("LA LIBERTAD")
    assert {e["ruc"] for e in r["empresas"]} == {"20990000001", "20990000002"}


def test_validaciones_de_entrada(datos_falsos):
    with pytest.raises(ToolError, match="departamento"):
        server.buscar_empresas("Atlantida")
    with pytest.raises(ToolError, match="Modalidad"):
        server.buscar_empresas("Lima", modalidad="drones")
    with pytest.raises(ToolError, match="11 digitos"):
        server.ficha_empresa("123")


def test_ficha_empresa_separa_fuentes_y_limpia_nan(datos_falsos):
    f = server.ficha_empresa("20990000001")
    modalidades = {a["modalidad"] for a in f["autorizaciones_sucamec"]["vigentes"]}
    assert "TECNOLOGIA - VIDEO A DISTANCIA" in modalidades   # CCTV verificable
    assert f["sunat"]["datos"]["condicion"] == "HABIDO"
    assert f["oece"]["datos"]["n_sanciones"] is None         # NaN -> None
    assert f["oece"]["fuente"].endswith("20990000001")
    json.dumps(f)


def test_ficha_empresa_ruc_desconocido(datos_falsos):
    with pytest.raises(ToolError, match="no aparece"):
        server.ficha_empresa("20111111111")


def test_contratos_respeta_el_limite_y_cita_cada_proceso(datos_falsos):
    r = server.contratos_vigilancia("La Libertad", limite=2)
    assert r["total"] == 5 and r["mostrados"] == 2
    assert all(c["fuente"].endswith(c["ocid"]) for c in r["contratos"])
    assert r["mediana_precio_puesto_mes"] == 30000.0
    json.dumps(r)


def test_benchmark_cae_al_nacional_con_pocos_contratos(datos_falsos):
    assert server.benchmark_precio("La Libertad")["alcance"] == "departamental"
    r = server.benchmark_precio("Cajamarca")
    assert r["alcance"] == "nacional" and r["n"] == 40 and "Cajamarca" in r["motivo"]


def test_evaluar_oferta_semaforo(datos_falsos):
    assert server.evaluar_oferta(2000, 24, "La Libertad")["color"] == "rojo"
    assert server.evaluar_oferta(11000, 24, "La Libertad")["estado"] == "en_rango"
    assert server.evaluar_oferta(30000, 24, "La Libertad")["estado"] == "sobre_mercado"
    with pytest.raises(ToolError):
        server.evaluar_oferta(0)


def test_riesgo_zona_por_provincia(datos_falsos):
    r = server.riesgo_zona("La Libertad", "Pataz")
    assert r["casos_provincia"] == 4
    assert r["conflictos_departamento"] == 5 and r["activos_departamento"] == 4
    assert r["ranking_departamento"] == 2
    assert isinstance(r["estados_emergencia"], list)
    assert r["nivel"] == "extraido"


def test_puntaje_confianza_sin_modulo_da_error(datos_falsos, monkeypatch):
    monkeypatch.setitem(sys.modules, "garita.confianza", None)   # el import falla
    with pytest.raises(ToolError, match="confianza"):
        server.puntaje_confianza("20990000001", "La Libertad")


def test_puntaje_confianza_pasa_el_desglose(datos_falsos, monkeypatch):
    falso = types.ModuleType("garita.confianza")
    falso.puntaje_confianza = lambda ruc, dep, mod, armas: {
        "ruc": ruc, "razon_social": "ANDES", "puntaje": 82.0,
        "componentes": [{"nombre": "autorizacion_sucamec", "puntos": 30, "maximo": 30,
                         "nivel": "verificado", "detalle": dep, "fuente": "https://x"}]}
    monkeypatch.setitem(sys.modules, "garita.confianza", falso)
    r = server.puntaje_confianza("20990000001", "La Libertad", armas="CON ARMAS")
    assert r["puntaje"] == 82.0 and r["componentes"][0]["detalle"] == "LA LIBERTAD"


def test_cliente_mcp_en_memoria(datos_falsos):
    """El mismo camino que usa Claude: llamada por el protocolo, no la funcion directa."""
    async def llamar():
        async with Client(server.mcp) as c:
            return await c.call_tool("costo_laboral_minimo", {"horas_dia": 12})
    r = asyncio.run(llamar())
    assert r.data["horas_puesto_dia"] == 12 and r.data["piso_puesto_mes"] > 0


# ------------------------------------------------------- las cuentas del precio
def test_piso_legal_ordenado_por_jornada():
    p24 = bm.costo_laboral_minimo(24).piso_puesto_mes
    p12 = bm.costo_laboral_minimo(12).piso_puesto_mes
    assert p24 > p12 > 0
    assert 3.5 < bm.costo_laboral_minimo(24).agentes_necesarios < 4.0


def test_precio_puesto_mes():
    assert bm.precio_puesto_mes(120000, 1, 12) == 10000.0
    assert bm.precio_puesto_mes(120000, bm.puestos_equivalentes_24h(n_12h=2), 12) == 10000.0
    assert bm.precio_puesto_mes(None, 1, 12) is None
    assert bm.precio_puesto_mes(120000, 0, 12) is None
    assert bm.precio_puesto_mes(120000, 1, None) is None
