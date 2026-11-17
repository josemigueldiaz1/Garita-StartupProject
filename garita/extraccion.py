"""
Normalizacion de contratos con el LLM: de las Bases en texto libre a puestos y horas.

Este es el insight de Garita. Las Bases dicen "12 agentes, 2 turnos, 365 dias" o
traen una tabla de puestos con OCR sucio; el LLM lo convierte en una lista de puestos
con sus horas, si van armados, el plazo y el perfil exigido (esquemas.ExtraccionTDR).
Con eso Python calcula soles por puesto-mes, un benchmark que hoy no existe.

La extraccion corre UNA vez en lote y se guarda; la app nunca la repite. Cada fila
guarda sus tokens y su costo, que son la base del costo por usuario del README.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .benchmark import puestos_equivalentes_24h
from .config import Config, configurar_logging, load_config
from .costos import TopeAlcanzado
from .esquemas import ExtraccionDocumento, ExtraccionTDR, PedidoTexto
from .llm import ClienteLLM, SinClave, cliente

log = logging.getLogger("garita.extraccion")

# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.7 Prompts: instrucciones para leer Bases, documentos y pedidos
SISTEMA_TDR = """Eres un analista de compras publicas del Peru especializado en servicios de
seguridad y vigilancia. Lees fragmentos de las Bases de un proceso del OECE (terminos de
referencia) y extraes como esta dimensionado el servicio.

Devuelves SIEMPRE un JSON valido con estos campos:
  "puede_extraer": bool, false si el texto no permite saber cuantos puestos hay
  "motivo": string, por que no se pudo (vacio si se pudo)
  "puestos": lista de {"descripcion": str, "cantidad": int, "horas_por_dia": number,
             "dias_por_semana": number, "armado": bool o null}
  "n_agentes_total": int o null (agentes en total, si el texto lo dice)
  "plazo_meses": number o null (duracion del servicio)
  "incluye_supervisor": bool o null
  "perfil": {"estatura_min_m": number o null, "edad_min": int o null, "edad_max": int o null,
             "experiencia_min_meses": int o null, "curso_sucamec": bool o null,
             "licencia_arma_l4": bool o null, "secundaria_completa": bool o null}
  "tipo_arma": string o null (ej. "revolver calibre 38")
  "equipamiento": lista de strings (radios, vehiculos, camaras, detectores, etc.)
  "confianza": "alta" | "media" | "baja"
  "evidencia": cita textual breve (max 300 caracteres) de donde sale el numero de puestos

REGLAS:
1. Un PUESTO es una posicion que se cubre en un horario (ej. "Puesto 1 - Puerta principal,
   24 horas"). No confundas puestos con agentes: un puesto 24 h lo cubren 2 o 3 agentes por
   turnos. Si el texto solo da agentes por turno, convierte: 2 agentes en turno de 12 h dia
   y noche en una misma puerta = 1 puesto de 24 h.
2. Si hay varias sedes o items, lista cada grupo de puestos por separado.
3. Los supervisores NO son puestos de vigilancia: marca incluye_supervisor y no los sumes.
4. armado = true si el puesto va con arma de fuego; false si dice sin arma; null si no dice.
5. No inventes. Si un dato no aparece, null. Si no hay forma de saber cuantos puestos hay,
   puede_extraer = false.
6. El texto viene de OCR y puede tener errores ("serv�cio", "tumo" por "turno"): interpretalos.
7. confianza "alta" solo si la cantidad de puestos y sus horas aparecen explicitas."""

USUARIO_TDR = """PROCESO: {ocid}
ENTIDAD: {entidad}
DESCRIPCION: {descripcion}
PLAZO DEL CONTRATO SEGUN OECE: {duracion_dias} dias

FRAGMENTOS DE LAS BASES (paginas seleccionadas):
{texto}

Devuelve el JSON."""

SISTEMA_DOC = """Lees un documento que un proveedor de seguridad privada entrega a su cliente en
el Peru: carta fianza, poliza de seguro, resolucion de autorizacion de SUCAMEC u otro. Extraes
los datos para controlar montos y vencimientos.

Devuelves SIEMPRE un JSON valido con: "tipo_documento" ("carta_fianza" | "poliza" |
"autorizacion_sucamec" | "contrato" | "otro"), "numero", "emisor", "empresa", "ruc_empresa",
"beneficiario", "monto" (number), "moneda" ("PEN" | "USD" | "otra"), "fecha_emision" y
"fecha_vencimiento" (formato AAAA-MM-DD), "objeto", "observaciones".

REGLAS: no inventes, usa null si falta. No extraigas nombres, DNI ni firmas de personas
naturales: solo empresas y entidades. Si el documento dice "SINTETICO" o "DEMO", indicalo
en observaciones."""

SISTEMA_PEDIDO = """Conviertes el pedido de un cliente que quiere contratar seguridad privada en el
Peru en un JSON con: "departamento", "provincia" (en mayusculas, sin tildes), "tipo_sitio"
("mina" | "campamento" | "puerto" | "planta" | "almacen" | "oficina" | "otro"), "modalidad"
("VIGILANCIA PRIVADA" | "PROTECCION PERSONAL" | "TRANSPORTE DE DINERO Y VALORES"),
"con_armas" (bool o null), "n_puestos", "horas_por_dia", "dias_por_semana", "plazo_meses",
"equipamiento" (lista) y "notas". Si mencionan una provincia o distrito conocido (ej. Pataz),
completa el departamento (La Libertad). 24/7 = 24 horas, 7 dias. No inventes: null si falta."""


def _fila_extraccion(fila, ext: ExtraccionTDR | None, uso: dict, error: str) -> dict:
    base = {"ocid": fila.ocid, "error": error, **{k: uso.get(k) for k in
            ("tokens_entrada", "tokens_salida", "costo_usd", "intentos")}}
    if ext is None:
        return base
    n24 = sum(p.cantidad for p in ext.puestos if p.horas_por_dia >= 20)
    n12 = sum(p.cantidad for p in ext.puestos if 10 <= p.horas_por_dia < 20)
    otros = [p for p in ext.puestos if p.horas_por_dia < 10]
    n_otros = sum(p.cantidad for p in otros)
    horas_otros = (sum(p.cantidad * p.horas_por_dia for p in otros) / n_otros) if n_otros else 8
    armados = {p.armado for p in ext.puestos}
    armado = ("si" if armados == {True} else "no" if armados == {False}
              else "mixto" if {True, False} <= armados else "no_indica")
    # Puestos que no se cubren los 7 dias valen menos horas: se ajusta por dias.
    equiv = sum(puestos_equivalentes_24h(*(
        (p.cantidad, 0, 0) if p.horas_por_dia >= 20 else
        (0, p.cantidad, 0) if p.horas_por_dia >= 10 else (0, 0, p.cantidad)),
        horas_otros=p.horas_por_dia) * (p.dias_por_semana / 7) for p in ext.puestos)
    return base | {
        "puede_extraer": ext.puede_extraer, "motivo": ext.motivo,
        "n_puestos": sum(p.cantidad for p in ext.puestos),
        "n_puestos_24h": n24, "n_puestos_12h": n12, "n_puestos_otros": n_otros,
        "puestos_equivalentes_24h": round(equiv, 3),
        "n_agentes": ext.n_agentes_total, "meses": ext.plazo_meses, "armado": armado,
        "incluye_supervisor": ext.incluye_supervisor,
        "estatura_min_m": ext.perfil.estatura_min_m, "edad_min": ext.perfil.edad_min,
        "edad_max": ext.perfil.edad_max,
        "experiencia_min_meses": ext.perfil.experiencia_min_meses,
        "curso_sucamec": ext.perfil.curso_sucamec,
        "licencia_arma_l4": ext.perfil.licencia_arma_l4,
        "tipo_arma": ext.tipo_arma, "equipamiento": " | ".join(ext.equipamiento),
        "confianza": ext.confianza, "evidencia": ext.evidencia,
        "puestos_json": ExtraccionTDR.model_validate(ext).model_dump_json(include={"puestos"}),
    }


def extraer_proceso(cli: ClienteLLM, fila) -> dict:
    usuario = USUARIO_TDR.format(ocid=fila.ocid, entidad=fila.entidad,
                                 descripcion=str(fila.descripcion)[:400],
                                 duracion_dias=fila.duracion_dias, texto=fila.texto_tdr)
    try:
        ext, uso = cli.estructurado(SISTEMA_TDR, usuario, ExtraccionTDR, tarea="extraer_tdr")
        return _fila_extraccion(fila, ext, uso, "")
    except (SinClave, TopeAlcanzado):
        raise
    except Exception as e:  # noqa: BLE001 - el proceso queda marcado y fuera del benchmark
        return _fila_extraccion(fila, None, {}, str(e)[:200])


# --- 08.8 Lote: extrae todos los procesos con texto de TDR, con cache por ocid
def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    log = configurar_logging("garita.extraccion")
    cli = cliente()
    ok, motivo = cli.disponible()
    if not ok:
        raise SinClave(motivo)
    textos = pd.read_parquet(cfg.processed_dir / "tdr_textos.parquet")
    contratos = pd.read_parquet(cfg.processed_dir / "contratos_vigilancia.parquet")
    t = textos[textos["caracteres"] > 500].merge(
        contratos[["ocid", "entidad", "descripcion", "duracion_dias"]], on="ocid", how="left")
    destino = cfg.processed_dir / "extracciones_llm.parquet"
    previas = pd.read_parquet(destino) if destino.exists() else pd.DataFrame(columns=["ocid", "error"])
    hechas = set(previas.loc[previas["error"].fillna("") == "", "ocid"])
    pendientes = t[~t["ocid"].isin(hechas)]
    log.info("Extraccion LLM: %d con texto, %d ya extraidos, %d pendientes (tope US$%.2f)",
             len(t), len(hechas), len(pendientes), cfg.tope_usd())
    filas = []
    try:
        with ThreadPoolExecutor(max_workers=int(cfg.llm["hilos"])) as ex:
            for i, f in enumerate(ex.map(lambda r: extraer_proceso(cli, r),
                                         pendientes.itertuples()), 1):
                filas.append(f)
                if i % 10 == 0 or i == len(pendientes):
                    log.info("  %d/%d · gastado US$%.4f", i, len(pendientes), cli.costos.total_usd())
    except TopeAlcanzado as e:
        log.warning("  %s Se guarda lo extraido hasta aqui.", e)
    tabla = pd.concat([previas[previas["ocid"].isin(hechas)], pd.DataFrame(filas)],
                      ignore_index=True)
    tabla.to_parquet(destino, index=False)
    resumen = {"extraidos": int((tabla["error"].fillna("") == "").sum()),
               "con_puestos": int((tabla.get("n_puestos", pd.Series(dtype=float)).fillna(0) > 0).sum()),
               "errores": int((tabla["error"].fillna("") != "").sum()),
               "costo_usd_lote": round(float(pd.DataFrame(filas).get("costo_usd", pd.Series(dtype=float)).sum()), 5)}
    log.info("Extraccion lista: %s", resumen)
    return resumen


# --- 08.9 En la app: leer un documento subido y entender un pedido en texto libre
def extraer_documento(texto: str) -> tuple[ExtraccionDocumento, dict]:
    return cliente().estructurado(SISTEMA_DOC, f"DOCUMENTO:\n{texto[:12000]}\n\nDevuelve el JSON.",
                                  ExtraccionDocumento, tarea="leer_documento")


def interpretar_pedido(texto: str) -> tuple[PedidoTexto, dict]:
    return cliente().estructurado(SISTEMA_PEDIDO, f"PEDIDO: {texto}\n\nDevuelve el JSON.",
                                  PedidoTexto, tarea="interpretar_pedido")
