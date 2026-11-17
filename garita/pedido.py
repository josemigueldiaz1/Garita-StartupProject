"""
El pedido del cliente y la solicitud de propuesta (RFP) que sale de el.

Todo lo que el cliente elige en la app (lugar, personal, perfil, armamento y
equipamiento) se guarda como un `Pedido`. De ahi salen la busqueda de proveedores, el
estimado de precio y la solicitud de propuesta en Word y Excel para enviar a las
empresas de la lista corta.

**Perfil del personal.** Estatura, edad, experiencia o idiomas son REQUISITOS del
cliente, no datos de personas: Garita no tiene ni guarda informacion de vigilantes. En
la solicitud, la empresa declara que los cumple; el nivel de ese dato es "declarado".

**Modo demo.** Si no hay clave del LLM, el texto libre del pedido se interpreta con
reglas (numeros, 24/7, "con armas", provincias conocidas). Es menos flexible que el
modelo, pero el flujo del demo nunca se cae.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

import pandas as pd

from .datos import normalizar, tabla

TIPOS_SITIO = ["mina", "campamento", "puerto", "planta", "almacen", "oficina", "otro"]
EQUIPAMIENTO = {
    # opcion -> autorizacion SUCAMEC que la respalda (None = solo declarada por la empresa).
    # SUCAMEC autoriza la tecnologia con una modalidad general ("tecnologia de seguridad");
    # las submodalidades del formulario (video, GPS, accesos) no tienen empresas registradas.
    "Radios de comunicacion": None,
    "Vehiculo de supervision": None,
    "Motocicleta para rondas": None,
    "Detector de metales": None,
    "Camaras con monitoreo a distancia (CCTV)": "TECNOLOGIA DE SEGURIDAD",
    "Control de accesos": "TECNOLOGIA DE SEGURIDAD",
    "Rastreo GPS de unidades": "TECNOLOGIA DE SEGURIDAD",
    "Central receptora de alarmas": "TECNOLOGIA DE SEGURIDAD",
}
ARMAS = ["Revolver calibre 38", "Pistola 9 mm", "Escopeta de perdigones", "Lo que defina la empresa"]


@dataclass
class Pedido:
    departamento: str = "LA LIBERTAD"
    provincia: str = "PATAZ"
    tipo_sitio: str = "campamento"
    modalidad: str = "VIGILANCIA PRIVADA"
    con_armas: bool = True
    tipo_arma: str = "Revolver calibre 38"
    n_puestos: int = 8
    horas_por_dia: int = 24
    dias_por_semana: int = 7
    plazo_meses: int = 12
    supervisor: bool = True
    estatura_min_m: float = 1.65
    edad_max: int = 50
    experiencia_min_meses: int = 12
    idiomas: list[str] = field(default_factory=lambda: ["Castellano"])
    licencia_conducir: bool = False
    curso_sucamec: bool = True
    equipamiento: list[str] = field(default_factory=lambda: ["Radios de comunicacion"])
    notas: str = ""
    creado: str = field(default_factory=lambda: datetime.now().isoformat(timespec="minutes"))

    @property
    def armas(self) -> str | None:
        return "CON ARMAS" if self.con_armas else None

    @property
    def puestos_equivalentes_24h(self) -> float:
        return self.n_puestos * self.horas_por_dia / 24 * self.dias_por_semana / 7

    def a_dict(self) -> dict:
        return asdict(self)


# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.10 Respaldo sin LLM: interpreta el pedido con reglas en modo demo
def interpretar_por_reglas(texto: str) -> dict:
    t = normalizar(texto)
    out: dict = {}
    m = re.search(r"(\d+)\s*(PUESTOS?|AGENTES?|VIGILANTES?)", t)
    if m:
        out["n_puestos"] = int(m.group(1))
    if re.search(r"24\s*/\s*7|24 HORAS|LAS 24", t):
        out.update(horas_por_dia=24, dias_por_semana=7)
    elif re.search(r"12\s*HORAS|DIURNO", t):
        out["horas_por_dia"] = 12
    if "SIN ARMA" in t:
        out["con_armas"] = False
    elif re.search(r"CON ARMA|ARMAD", t):
        out["con_armas"] = True
    m = re.search(r"(\d+)\s*MESES", t)
    if m:
        out["plazo_meses"] = int(m.group(1))
    # "campamento minero" es un campamento: los sitios explicitos van antes que "mina",
    # que tambien se activa con "minero" y por eso queda al final.
    for sitio in [s for s in TIPOS_SITIO if s != "mina"] + ["mina"]:
        if re.search(rf"\b{normalizar(sitio)}", t) or (sitio == "mina" and "MINER" in t):
            out["tipo_sitio"] = sitio
            break
    cent = tabla("centroides_distritos")
    if not cent.empty:
        provs = cent[["departamento", "provincia"]].drop_duplicates()
        for r in provs.itertuples():
            if re.search(rf"\b{re.escape(r.provincia)}\b", t) and r.provincia != r.departamento:
                out.update(departamento=r.departamento, provincia=r.provincia)
                break
        if "departamento" not in out:
            for d in sorted(provs["departamento"].unique(), key=len, reverse=True):
                if re.search(rf"\b{re.escape(d)}\b", t):
                    out["departamento"] = d
                    break
    return out


# --- 08.11 Respaldo sin LLM: fechas y montos de un documento con expresiones regulares
def documento_por_reglas(texto: str) -> dict:
    fechas = []
    for d, mth, y in re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", texto):
        try:
            fechas.append(date(int(y), int(mth), int(d)))
        except ValueError:
            pass
    montos = [float(x.replace(",", "")) for x in
              re.findall(r"S/\.?\s*([\d,]+(?:\.\d{2})?)", texto)]
    t = normalizar(texto)
    tipo = ("carta_fianza" if "FIANZA" in t else "poliza" if "POLIZA" in t
            else "autorizacion_sucamec" if "SUCAMEC" in t else "otro")
    return {"tipo_documento": tipo, "monto": max(montos) if montos else None,
            "moneda": "PEN" if montos else None,
            "fecha_emision": min(fechas).isoformat() if fechas else None,
            "fecha_vencimiento": max(fechas).isoformat() if fechas else None,
            "observaciones": "Leido por reglas (modo demo, sin LLM): verificar."}


# --- Salidas: solicitud de propuesta en Word y Excel, y vencimientos en calendario
def _requisitos(p: Pedido) -> list[tuple[str, str]]:
    eq = ", ".join(p.equipamiento) or "No requerido"
    return [
        ("Lugar", f"{p.tipo_sitio.title()} en {p.provincia.title()}, {p.departamento.title()}"),
        ("Modalidad", f"{p.modalidad.title()} {'con armas' if p.con_armas else 'sin armas'}"),
        ("Puestos", f"{p.n_puestos} puestos de {p.horas_por_dia} h, {p.dias_por_semana} dias por semana"),
        ("Plazo", f"{p.plazo_meses} meses"),
        ("Supervision", "Supervisor de turno incluido" if p.supervisor else "Sin supervisor dedicado"),
        ("Armamento", p.tipo_arma if p.con_armas else "No aplica"),
        ("Perfil minimo", f"Estatura minima {p.estatura_min_m:.2f} m; edad maxima {p.edad_max} anos; "
                          f"experiencia minima {p.experiencia_min_meses} meses; idiomas: "
                          f"{', '.join(p.idiomas) or 'castellano'}; "
                          f"{'licencia de conducir; ' if p.licencia_conducir else ''}"
                          f"{'curso SUCAMEC vigente' if p.curso_sucamec else ''}"),
        ("Equipamiento", eq),
        ("Notas del cliente", p.notas or "—"),
    ]


DOCUMENTOS_EXIGIDOS = [
    "Resolucion de autorizacion SUCAMEC vigente para la modalidad y el departamento",
    "Ficha RUC activa y habida (SUNAT)",
    "Carta fianza de fiel cumplimiento (10% del monto anual)",
    "Polizas SCTR (salud y pension) y Vida Ley del personal asignado",
    "Estructura de costos por puesto con planilla en regimen general (sueldo, cargas y beneficios)",
    "Declaracion jurada de cumplimiento del perfil exigido (nivel: declarado)",
    "Plan de contingencia y protocolo de relevo de turnos",
]


def solicitud_docx(p: Pedido, empresas: pd.DataFrame, precio: dict, piso: float) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("Solicitud de propuesta: servicio de seguridad privada", 0)
    doc.add_paragraph(f"Fecha: {date.today():%d/%m/%Y} · Generada con Garita")
    doc.add_heading("1. Requerimiento", 1)
    t = doc.add_table(rows=0, cols=2)
    t.style = "Light Grid Accent 1"
    for k, v in _requisitos(p):
        c = t.add_row().cells
        c[0].text, c[1].text = k, v
    doc.add_heading("2. Documentos que debe adjuntar la propuesta", 1)
    for d in DOCUMENTOS_EXIGIDOS:
        doc.add_paragraph(d, style="List Bullet")
    doc.add_heading("3. Referencia de precio", 1)
    if precio:
        doc.add_paragraph(
            f"Contratos publicos de vigilancia comparables ({precio.get('alcance', '')}, n = {precio.get('n')}): "
            f"mediana S/ {precio.get('mediana', 0):,.0f} por puesto 24/7 y mes; rango intercuartil "
            f"S/ {precio.get('p25', 0):,.0f} a S/ {precio.get('p75', 0):,.0f}. Fuente: OECE, contratos "
            f"normalizados por Garita.")
    doc.add_paragraph(
        f"Piso legal estimado de un puesto 24/7: S/ {piso:,.0f} al mes (remuneracion minima, recargo "
        f"nocturno, cargas sociales y beneficios). Las ofertas por debajo de ese monto deberan sustentar "
        f"su estructura de costos.")
    doc.add_heading("4. Empresas invitadas", 1)
    if not empresas.empty:
        t2 = doc.add_table(rows=1, cols=4)
        t2.style = "Light Grid Accent 1"
        for c, h in zip(t2.rows[0].cells, ["Empresa", "RUC", "Puntaje Garita", "Autorizacion vence"]):
            c.text = h
        for r in empresas.itertuples():
            c = t2.add_row().cells
            c[0].text, c[1].text, c[2].text = r.razon_social, r.ruc, str(r.puntaje)
            c[3].text = pd.Timestamp(r.vence).strftime("%d/%m/%Y") if pd.notna(r.vence) else ""
    doc.add_heading("5. Criterios de evaluacion", 1)
    for c in ["Cumplimiento documentario y autorizacion vigente (descalificante)",
              "Precio por puesto-mes y sustento de la estructura de costos (40%)",
              "Experiencia en servicios similares (25%)",
              "Plan de operacion, supervision y relevo (20%)",
              "Cobertura y tiempo de respuesta en la zona (15%)"]:
        doc.add_paragraph(c, style="List Number")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def solicitud_xlsx(p: Pedido, empresas: pd.DataFrame, precio: dict, piso: float) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(_requisitos(p), columns=["Campo", "Requisito"]).to_excel(
            xw, sheet_name="Requerimiento", index=False)
        pd.DataFrame({"Documento exigido": DOCUMENTOS_EXIGIDOS}).to_excel(
            xw, sheet_name="Documentos", index=False)
        cols = [c for c in ["razon_social", "ruc", "puntaje", "armas", "vence", "provincias_sede",
                            "km_al_sitio"] if c in empresas]
        empresas[cols].to_excel(xw, sheet_name="Empresas invitadas", index=False)
        pd.DataFrame([{"Concepto": "Mediana por puesto 24/7-mes", "Soles": precio.get("mediana")},
                      {"Concepto": "Percentil 25", "Soles": precio.get("p25")},
                      {"Concepto": "Percentil 75", "Soles": precio.get("p75")},
                      {"Concepto": "Piso legal puesto 24/7-mes", "Soles": piso}]).to_excel(
            xw, sheet_name="Referencia de precio", index=False)
        pd.DataFrame([{"Empresa": r.razon_social, "RUC": r.ruc, "Precio por puesto-mes": None,
                       "Total mensual": None, "Cumple documentos": None, "Observaciones": None}
                      for r in empresas.itertuples()]).to_excel(
            xw, sheet_name="Comparativo de ofertas", index=False)
    return buf.getvalue()


def calendario_ics(eventos: list[tuple[str, date, str]]) -> bytes:
    """Vencimientos como eventos de dia completo con aviso 30 dias antes."""
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Garita//Vencimientos//ES"]
    for i, (titulo, dia, detalle) in enumerate(eventos):
        lineas += ["BEGIN:VEVENT", f"UID:garita-{i}-{dia:%Y%m%d}@garita",
                   f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
                   f"DTSTART;VALUE=DATE:{dia:%Y%m%d}", f"SUMMARY:{titulo}",
                   f"DESCRIPTION:{detalle}", "BEGIN:VALARM", "TRIGGER:-P30D", "ACTION:DISPLAY",
                   f"DESCRIPTION:{titulo}", "END:VALARM", "END:VEVENT"]
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas).encode("utf-8")
