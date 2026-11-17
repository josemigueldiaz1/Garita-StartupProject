"""
Servidor MCP de Garita: los datos de Garita dentro de Claude.

    uv run mcp_server/server.py                                   # el servidor, por stdio
    claude mcp add --scope project garita -- uv run mcp_server/server.py
    uv run pytest tests/test_mcp.py                               # el contrato del servidor

Un analista de compras instala este servidor y la skill `evaluar-proveedor-seguridad`
y le pide a Claude "evalua estas tres propuestas de vigilancia para Pataz". El MCP
pone los datos (autorizaciones SUCAMEC, contratos del OECE, riesgo por zona) y la
skill pone el metodo.

Tres decisiones que hay que saber defender:

1. **Las cuentas las hace Python, no el modelo.** El precio por puesto-mes, el piso
   legal y el semaforo de una oferta salen de garita/benchmark.py. El modelo solo
   decide que herramienta llamar y como presentarlo; asi cada cifra se puede repetir.

2. **Cada respuesta dice de donde sale y que tan firme es.** Lleva `fuente` (URL) y
   `nivel`: verificado (fuente oficial), extraido (leido por Garita de un PDF oficial
   con OCR o LLM), declarado (lo dice la empresa) o sintetico (demo). Es la misma
   regla que la app: nunca se presenta un dato declarado como verificado.

3. **Solo lectura y sin red.** Todo sale de data/processed, versionado en el repo.
   Si el pipeline aun no corrio, la herramienta lo dice con un ToolError en vez de
   devolver una lista vacia que el modelo leeria como "no hay empresas".
"""

from __future__ import annotations

import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# `uv run mcp_server/server.py` pone mcp_server/ en sys.path, no la raiz del repo.
# Sin esta linea el paquete garita no se importa ni en local ni instalado como plugin.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
from fastmcp import FastMCP  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

from garita import benchmark as bm  # noqa: E402
from garita import datos  # noqa: E402
from garita.config import load_config  # noqa: E402

CFG = load_config()

# Los 25 departamentos del <select> de SUCAMEC (config.yaml). Son la forma canonica.
DEPARTAMENTOS = [datos.normalizar(d) for d in CFG.sucamec["departamentos"]]
MODALIDADES = sorted(set(CFG.sucamec["modalidades"].values()))

FUENTES = {
    "sucamec": CFG.sucamec["url"],
    "sucamec_publica": CFG.sucamec["pagina_publica"],
    "oece_record": CFG.oece["api_base"] + "/record/{ocid}",
    "oece_ficha": CFG.oece["ficha_publica"],
    "sunat": CFG.sunat["padron_url"],
    "defensoria": CFG.defensoria["indice"],
    "rmv": CFG.costo_laboral["rmv_fuente"],
}

# ===== HERRAMIENTA 04 · MCP =====
# --- 04.1 Servidor: nombre, instrucciones de uso y anotaciones de solo lectura
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": False}

mcp = FastMCP("garita", instructions=(
    "Datos de Garita para contratar seguridad privada en el Peru: empresas autorizadas por "
    "SUCAMEC, contratos publicos de vigilancia del OECE con su precio por puesto-mes, el piso "
    "legal de un puesto y los conflictos sociales por provincia de la Defensoria del Pueblo. "
    "Orden sugerido: buscar_empresas (quien esta autorizado), puntaje_confianza y ficha_empresa "
    "(que tan confiable es), benchmark_precio y contratos_vigilancia (cuanto cuesta), "
    "evaluar_oferta (si una oferta es sospechosa) y riesgo_zona (contexto del sitio). "
    "No calcules precios a mano: usa las herramientas. Cita siempre la fuente y el nivel de "
    "cada dato (verificado, extraido, declarado o sintetico) y nunca presentes un dato declarado "
    "o sintetico como verificado. Garita no tiene datos de vigilantes: no los pidas ni los inventes."))


# --- 04.3 Salidas: de DataFrame a JSON limpio (fechas ISO, NaN -> None)
def _valor(v: Any) -> Any:
    """Convierte un valor de pandas o numpy a un tipo que JSON entiende."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [_valor(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _valor(x) for k, x in v.items()}
    if hasattr(v, "tolist") and not isinstance(v, (str, bytes)):  # numpy array o escalar
        return _valor(v.tolist())
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def _registros(df: pd.DataFrame, limite: int, columnas: list[str] | None = None) -> list[dict]:
    """Primeras `limite` filas como lista de dicts. Solo las columnas que existan."""
    if df is None or df.empty:
        return []
    if columnas:
        df = df[[c for c in columnas if c in df.columns]]
    return [{k: _valor(v) for k, v in fila.items()} for fila in df.head(limite).to_dict("records")]


def _sin_datos(nombre: str, paso: str) -> None:
    """ToolError si la tabla aun no existe: el pipeline no ha corrido."""
    if datos.tabla(nombre).empty:
        raise ToolError(
            f"Garita aun no tiene datos procesados de '{nombre}'. Hay que correr el pipeline: "
            f"uv run python run_pipeline.py --pasos {paso}")


def _departamento(texto: str) -> str:
    dep = datos.normalizar(texto)
    if dep in ("LIMA METROPOLITANA", "LIMA PROVINCIAS"):
        dep = "LIMA"
    if dep not in DEPARTAMENTOS:
        raise ToolError(f"No reconozco el departamento {texto!r}. Usa uno de: {', '.join(DEPARTAMENTOS)}.")
    return dep


def _modalidad(texto: str) -> str:
    m = datos.normalizar(texto)
    if m not in MODALIDADES:
        raise ToolError(f"Modalidad {texto!r} no existe en el registro. Usa una de: {', '.join(MODALIDADES)}.")
    return m


def _armas(texto: str | None) -> str | None:
    if texto is None or str(texto).strip() == "":
        return None
    a = datos.normalizar(texto)
    if a in ("CON ARMAS", "ARMADO", "SI", "CON ARMA"):
        return "CON ARMAS"
    if a in ("SIN ARMAS", "NO", "SIN ARMA"):
        return "SIN ARMAS"
    raise ToolError("armas debe ser 'CON ARMAS', 'SIN ARMAS' o vacio (cualquiera).")


def _ruc(texto: str) -> str:
    r = "".join(ch for ch in str(texto) if ch.isdigit())
    if len(r) != 11:
        raise ToolError(f"El RUC debe tener 11 digitos; recibi {texto!r}.")
    return r


# --- 04.2 Herramientas de consulta: empresas autorizadas y su ficha
@mcp.tool(annotations=SOLO_LECTURA)
def buscar_empresas(departamento: str, modalidad: str = "VIGILANCIA PRIVADA",
                    armas: str | None = None, provincia: str | None = None,
                    limite: int = 30) -> dict:
    """Empresas con sede autorizada y vigente por SUCAMEC en un departamento y modalidad.

    departamento: uno de los 25 del Peru (ej. "La Libertad"). modalidad: "VIGILANCIA PRIVADA",
    "PROTECCION PERSONAL", "TRANSPORTE DE DINERO Y VALORES", "TECNOLOGIA - VIDEO A DISTANCIA",
    "TECNOLOGIA - GPS", "TECNOLOGIA - CONTROL DE ACCESOS", etc. armas: "CON ARMAS" exige
    autorizacion con armas; vacio acepta cualquiera. provincia: si se da, primero salen las
    empresas con sede en esa provincia. Una empresa que no aparece aqui NO esta autorizada
    para ese departamento y modalidad: descartala y dilo.
    """
    _sin_datos("sucamec_resoluciones", "sucamec")
    dep, mod, arm = _departamento(departamento), _modalidad(modalidad), _armas(armas)
    df = datos.buscar_empresas(dep, mod, armas=arm, provincia=provincia)
    if not df.empty:
        df = df.sort_values(["sede_en_provincia", "vencimiento"], ascending=[False, False])
    empresas = _registros(df, max(1, min(int(limite), 100)), [
        "ruc", "razon_social", "armas", "vencimiento", "provincias_sede",
        "sede_en_provincia", "resoluciones", "direccion"])
    return {
        "departamento": dep, "modalidad": mod, "armas": arm or "CUALQUIERA",
        "provincia": datos.normalizar(provincia) if provincia else None,
        "total": int(len(df)), "mostradas": len(empresas), "empresas": empresas,
        "nivel": "verificado", "fuente": FUENTES["sucamec"],
        "nota": ("La autorizacion se verifica por sede: la empresa tiene una sede autorizada en el "
                 "departamento. 'vencimiento' es la autorizacion vigente que vence antes."),
    }


@mcp.tool(annotations=SOLO_LECTURA)
def ficha_empresa(ruc: str) -> dict:
    """Todo lo que Garita sabe de una empresa de seguridad por su RUC, separado por fuente.

    Devuelve sus autorizaciones SUCAMEC (modalidad, sede, vencimiento), su estado y condicion
    en SUNAT, su ficha del buscador de proveedores del OECE (apto para contratar, penalidades,
    sanciones) y su experiencia en contratos publicos de vigilancia. Sirve para verificar
    servicios de tecnologia (CCTV, GPS, control de accesos): son modalidades SUCAMEC propias.
    """
    _sin_datos("sucamec_resoluciones", "sucamec")
    r = _ruc(ruc)
    f = datos.ficha_empresa(r)
    if not f["autorizaciones"] and not any(f[k] for k in ("empresa", "sunat", "oece", "experiencia_publica")):
        raise ToolError(f"El RUC {r} no aparece en los datos de Garita: no tiene autorizacion "
                        "SUCAMEC vigente ni contratos publicos de vigilancia registrados.")
    return {
        "ruc": r,
        "empresa": _valor(f["empresa"]),
        "autorizaciones_sucamec": {
            "nivel": "verificado", "fuente": FUENTES["sucamec"],
            "vigentes": _registros(pd.DataFrame(f["autorizaciones"]), 50, [
                "modalidad", "armas", "departamento", "provincia", "sede", "resolucion",
                "fecha_vencimiento"]),
        },
        "sunat": {"nivel": "verificado", "fuente": FUENTES["sunat"], "datos": _valor(f["sunat"])},
        "oece": {"nivel": "verificado", "fuente": FUENTES["oece_ficha"].format(ruc=r),
                 "datos": _valor(f["oece"])},
        "experiencia_publica": {"nivel": "verificado",
                                "fuente": CFG.oece["api_base"] + "/files",
                                "datos": _valor(f["experiencia_publica"])},
        "no_disponible": ("Deuda coactiva, centrales de riesgo y sanciones SUNAFIL no tienen descarga "
                          "publica: son integracion futura. Polizas y carta fianza las sube el proveedor."),
    }


# --- 04.4 Herramientas de precio: contratos, benchmark, piso legal y semaforo de una oferta
@mcp.tool(annotations=SOLO_LECTURA)
def contratos_vigilancia(departamento: str | None = None, limite: int = 20) -> dict:
    """Contratos publicos de vigilancia con su precio por puesto 24/7 equivalente y mes.

    El monto y las fechas salen del OECE (verificado); los puestos, turnos y si es armado los
    leyo Garita de las Bases del proceso con OCR y un LLM (extraido), con una cita textual en
    `evidencia`. Un puesto de 12 horas cuenta como medio puesto 24/7.
    """
    _sin_datos("benchmark_contratos", "benchmark")
    dep = _departamento(departamento) if departamento else None
    df = datos.contratos_vigilancia(dep)
    filas = _registros(df, max(1, min(int(limite), 100)), [
        "ocid", "entidad", "departamento", "proveedor", "ruc_proveedor", "monto_contrato",
        "fecha_firma", "duracion_dias", "meses", "n_puestos_24h", "n_puestos_12h",
        "puestos_equivalentes_24h", "armado", "precio_puesto_mes", "confianza", "evidencia",
        "url_bases"])
    for f in filas:
        f["fuente"] = FUENTES["oece_record"].format(ocid=f.get("ocid"))
    precios = df["precio_puesto_mes"].dropna() if "precio_puesto_mes" in df else pd.Series(dtype=float)
    return {
        "departamento": dep or "PERU", "total": int(len(df)), "mostrados": len(filas),
        "mediana_precio_puesto_mes": _valor(round(float(precios.median()), 2)) if len(precios) else None,
        "contratos": filas,
        "nivel": {"monto_y_fechas": "verificado", "puestos_turnos_armado": "extraido",
                  "precio_puesto_mes": "extraido (calculado con puestos extraidos)"},
        "fuente": CFG.oece["api_base"],
    }


@mcp.tool(annotations=SOLO_LECTURA)
def benchmark_precio(departamento: str | None = None) -> dict:
    """Rango de precio (percentiles 25, 50 y 75) por puesto 24/7 y mes en un departamento.

    Si el departamento tiene menos de 3 contratos validos devuelve el rango nacional y lo dice
    en `alcance` y `motivo`. Para un puesto de 12 horas, multiplica por 0.5; mejor aun, usa
    evaluar_oferta con horas_dia=12.
    """
    _sin_datos("benchmark_departamento", "benchmark")
    dep = _departamento(departamento) if departamento else None
    b = datos.benchmark(dep)
    if not b:
        raise ToolError("No hay benchmark nacional disponible: corre el paso benchmark del pipeline.")
    piso = bm.costo_laboral_minimo(24, cfg=CFG)
    return {
        **{k: _valor(v) for k, v in b.items()},
        "piso_legal_24h": piso.piso_puesto_mes,
        "unidad": "soles por puesto 24/7 equivalente y mes",
        "nivel": "extraido", "fuente": CFG.oece["api_base"],
        "metodo": "monto del contrato / (puestos 24/7 equivalentes x meses), con puestos leidos de las Bases",
    }


@mcp.tool(annotations=SOLO_LECTURA)
def costo_laboral_minimo(horas_dia: int = 24, dias_semana: int = 7) -> dict:
    """Piso legal mensual de un puesto de vigilancia: lo minimo que cuesta cubrirlo con planilla.

    Suma la remuneracion minima vital, el recargo nocturno, EsSalud, SCTR, vida ley,
    gratificaciones, CTS y vacaciones, por los agentes que hacen falta para cubrir el puesto
    (3.8 para un puesto 24/7), mas un margen minimo de la empresa. Una oferta por debajo solo
    cierra si no se paga planilla completa: es senal de informalidad, no una prueba.
    """
    if not 1 <= int(horas_dia) <= 24 or not 1 <= int(dias_semana) <= 7:
        raise ToolError("horas_dia va de 1 a 24 y dias_semana de 1 a 7.")
    c = bm.costo_laboral_minimo(int(horas_dia), int(dias_semana), cfg=CFG)
    return {**_valor(c.a_dict()), "unidad": "soles por puesto y mes",
            "nivel": {"rmv": "verificado", "cargas_y_provisiones": "supuesto legal (config.yaml)"},
            "fuente": FUENTES["rmv"]}


@mcp.tool(annotations=SOLO_LECTURA)
def evaluar_oferta(precio_puesto_mes: float, horas_dia: int = 24,
                   departamento: str | None = None) -> dict:
    """Semaforo de una oferta: compara su precio por puesto y mes con el piso legal y el mercado.

    precio_puesto_mes: lo que cobra la empresa por UN puesto de `horas_dia` horas al mes.
    Si la oferta trae un monto total, primero divide entre puestos y meses (o usa el script
    precio_puesto.py de la skill). estado: "bajo_piso" (rojo: no cubre la planilla minima),
    "bajo_mercado" (ambar: debajo del percentil 25), "en_rango" o "sobre_mercado".
    """
    if precio_puesto_mes is None or float(precio_puesto_mes) <= 0:
        raise ToolError("precio_puesto_mes debe ser un monto positivo en soles.")
    if not 1 <= int(horas_dia) <= 24:
        raise ToolError("horas_dia va de 1 a 24.")
    dep = _departamento(departamento) if departamento else None
    b = datos.benchmark(dep) if not datos.tabla("benchmark_departamento").empty else {}
    r = bm.evaluar_oferta(float(precio_puesto_mes), int(horas_dia), benchmark=b or None, cfg=CFG)
    colores = {"bajo_piso": "rojo", "bajo_mercado": "ambar", "en_rango": "verde", "sobre_mercado": "azul"}
    return {
        **_valor(r), "color": colores[r["estado"]], "horas_dia": int(horas_dia),
        "departamento": dep or "PERU",
        "alcance_benchmark": b.get("alcance") if b else "sin benchmark",
        "nivel": {"precio_ofertado": "declarado", "piso_legal": "calculado con la RMV verificada",
                  "rango_mercado": "extraido"},
        "fuente": {"piso_legal": FUENTES["rmv"], "mercado": CFG.oece["api_base"]},
    }


# --- 04.5 Herramientas de contexto: riesgo de la zona y puntaje de confianza
@mcp.tool(annotations=SOLO_LECTURA)
def riesgo_zona(departamento: str, provincia: str | None = None) -> dict:
    """Riesgo de la zona: conflictos sociales (Defensoria) y estados de emergencia vigentes.

    Devuelve el conteo oficial del departamento (Cuadro 3 del reporte: total, activos,
    latentes y su puesto entre los 25), los casos que el reporte ubica en la provincia (un
    minimo: el reporte 2026 no lista todos) y los estados de emergencia vigentes con su
    decreto supremo. Es contexto para dimensionar el servicio, no una prediccion de incidentes.
    """
    _sin_datos("conflictos_provincia", "defensoria")
    dep = _departamento(departamento)
    r = datos.riesgo_zona(dep, provincia)
    return {**_valor(r), "nivel": "extraido", "fuente": FUENTES["defensoria"],
            "nota": "Conteos leidos del reporte mensual de conflictos sociales (PDF) de la Defensoria."}


@mcp.tool(annotations=SOLO_LECTURA)
def puntaje_confianza(ruc: str, departamento: str, modalidad: str = "VIGILANCIA PRIVADA",
                      armas: str | None = None) -> dict:
    """Puntaje de confianza de 0 a 100 de una empresa para un servicio concreto, con su desglose.

    Cada componente trae sus puntos, su maximo, su nivel y su fuente: autorizacion SUCAMEC para
    ese departamento y modalidad, vigencia restante, RUC activo y habido en SUNAT, apto para
    contratar con el Estado, penalidades, experiencia en contratos publicos y cobertura. Muestra
    siempre el desglose, no solo el numero final.
    """
    _sin_datos("sucamec_resoluciones", "sucamec")
    r, dep, mod, arm = _ruc(ruc), _departamento(departamento), _modalidad(modalidad), _armas(armas)
    try:
        from garita.confianza import puntaje_confianza as calcular
    except ImportError as e:
        raise ToolError("El modulo de puntaje (garita/confianza.py) aun no esta disponible en esta "
                        "version de Garita. Usa ficha_empresa mientras tanto.") from e
    resultado = calcular(r, dep, mod, arm)
    if not resultado:
        raise ToolError(f"No hay datos para puntuar el RUC {r}.")
    return _valor(resultado)


# --- 04.6 Arranque: stdio, que es lo que usan Claude Code y Claude Desktop
if __name__ == "__main__":
    mcp.run()
