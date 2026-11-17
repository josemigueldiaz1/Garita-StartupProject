"""
Precio por puesto-mes y costo laboral minimo de un puesto de vigilancia.

Las dos cuentas son aritmetica, no criterio, asi que las hace Python y nunca el LLM.
El LLM solo lee las Bases y devuelve cuantos puestos hay y de cuantas horas; con eso
este modulo calcula el precio. La skill del producto y el MCP llaman a estas mismas
funciones.

**El costo laboral minimo** es el piso legal de lo que cuesta cubrir un puesto: la
remuneracion minima vital, el recargo nocturno, las cargas sociales y las provisiones
(gratificaciones, CTS y vacaciones). Una oferta por debajo de ese piso solo cierra si
la empresa no paga planilla completa: es una senal de informalidad, no una prueba.
Los supuestos estan en config.yaml -> costo_laboral y se muestran en la app.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from .config import Config, load_config

DIAS_POR_MES = 365 / 12


@dataclass
class CostoLaboral:
    """Desglose del piso legal de un puesto. Todo en soles por mes."""

    horas_puesto_dia: int
    horas_puesto_mes: float
    horas_efectivas_agente_mes: float
    agentes_necesarios: float
    sueldo_promedio_agente: float
    costo_agente_mes: float
    costo_planilla_puesto: float
    margen_minimo: float
    piso_puesto_mes: float
    supuestos: dict

    def a_dict(self) -> dict:
        return asdict(self)


# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.5 Calculo: la aritmetica del benchmark la hace Python, no el modelo
def costo_laboral_minimo(horas_dia: int = 24, dias_semana: int = 7,
                         cfg: Config | None = None) -> CostoLaboral:
    """
    Piso legal mensual de un puesto que se cubre `horas_dia` horas, `dias_semana` dias.

    Agentes necesarios = horas del puesto en el mes / horas efectivas de un agente.
    Las horas efectivas descuentan el mes de vacaciones: 48 h x 52 semanas / 12 meses
    x 11/12. Un puesto 24/7 necesita asi 3.8 agentes, no 3: cubrirlo con 3 exige
    horas extra, que cuestan 25% o 35% mas, asi que nunca bajan el piso.
    """
    cfg = cfg or load_config()
    c = cfg.costo_laboral
    rmv = float(c["rmv"])

    horas_puesto_mes = horas_dia * dias_semana * 52 / 12
    horas_efectivas = c["horas_semanales_max"] * 52 / 12 * (11 / 12)
    agentes = horas_puesto_mes / horas_efectivas

    # Fraccion nocturna: de 10 p. m. a 6 a. m. son 8 de las 24 horas. Un puesto de
    # 12 h diurno no la tiene; uno de 24 h tiene un tercio de sus horas de noche.
    fraccion_nocturna = 8 / 24 if horas_dia >= 24 else (4 / 12 if horas_dia > 16 else 0.0)
    sueldo = rmv * (1 + c["recargo_nocturno_pct"] * fraccion_nocturna)
    if c.get("incluir_asignacion_familiar", False):
        sueldo += rmv * c["asignacion_familiar_pct"]

    cargas = c["essalud_pct"] + c["sctr_pct"] + c["vida_ley_pct"]
    provisiones = (c["gratificaciones_por_anio"] * (1 + c["bonificacion_extraordinaria_pct"])
                   + c["cts_sueldos_por_anio"] + c["vacaciones_sueldos_por_anio"]) / 12
    costo_agente = sueldo * (1 + cargas + provisiones)

    planilla = costo_agente * agentes
    margen = planilla * c["margen_minimo_empresa_pct"]
    return CostoLaboral(
        horas_puesto_dia=horas_dia,
        horas_puesto_mes=round(horas_puesto_mes, 1),
        horas_efectivas_agente_mes=round(horas_efectivas, 1),
        agentes_necesarios=round(agentes, 2),
        sueldo_promedio_agente=round(sueldo, 2),
        costo_agente_mes=round(costo_agente, 2),
        costo_planilla_puesto=round(planilla, 2),
        margen_minimo=round(margen, 2),
        piso_puesto_mes=round(planilla + margen, 2),
        supuestos={"rmv": rmv, "rmv_fuente": c["rmv_fuente"],
                   "cargas_sociales_pct": round(cargas * 100, 2),
                   "provisiones_pct": round(provisiones * 100, 2),
                   "fraccion_nocturna": round(fraccion_nocturna, 3),
                   "margen_minimo_pct": c["margen_minimo_empresa_pct"] * 100},
    )


def puestos_equivalentes_24h(n_24h: float = 0, n_12h: float = 0, n_otros: float = 0,
                             horas_otros: float = 8) -> float:
    """Convierte puestos de distinta jornada a puestos 24/7 equivalentes por horas."""
    return (n_24h or 0) + (n_12h or 0) * 0.5 + (n_otros or 0) * (horas_otros or 8) / 24


def precio_puesto_mes(monto: float, puestos_24h_equiv: float, meses: float) -> float | None:
    """Soles por puesto 24/7 equivalente y mes. None si faltan datos para dividir."""
    if not monto or not puestos_24h_equiv or not meses or puestos_24h_equiv <= 0 or meses <= 0:
        return None
    return round(float(monto) / (float(puestos_24h_equiv) * float(meses)), 2)


def evaluar_oferta(precio_ofertado_puesto_mes: float, horas_dia: int = 24,
                   benchmark: dict | None = None, cfg: Config | None = None) -> dict:
    """
    Ubica una oferta frente al piso legal y al benchmark del departamento.

    Devuelve el semaforo que pinta la app y que la skill marca en rojo:
    `bajo_piso` (rojo), `bajo_mercado` (ambar, debajo del percentil 25), `en_rango`
    o `sobre_mercado` (encima del percentil 75).
    """
    piso = costo_laboral_minimo(horas_dia=horas_dia, cfg=cfg)
    factor = horas_dia / 24
    resultado = {"precio": precio_ofertado_puesto_mes,
                 "piso_legal": round(piso.piso_puesto_mes, 2), "estado": "en_rango"}
    if precio_ofertado_puesto_mes < piso.piso_puesto_mes:
        resultado["estado"] = "bajo_piso"
    elif benchmark and benchmark.get("n", 0) >= 3:
        p25, p75 = benchmark["p25"] * factor, benchmark["p75"] * factor
        resultado.update({"p25": round(p25, 2), "p75": round(p75, 2)})
        if precio_ofertado_puesto_mes < p25:
            resultado["estado"] = "bajo_mercado"
        elif precio_ofertado_puesto_mes > p75:
            resultado["estado"] = "sobre_mercado"
    return resultado
