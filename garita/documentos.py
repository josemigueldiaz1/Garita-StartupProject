"""
Document AI: leer las Bases de los contratos y los documentos que suben los clientes.

Sigue la regla de oro de la sesion 10 (triaje.py): **OCR solo en las paginas que son
imagen**. En el resto, extraccion directa de la capa de texto, que es gratis e
instantanea. Unas Bases tipicas tienen 40 a 140 paginas; casi todas traen capa de texto
(aunque con errores de un OCR antiguo) y unas pocas son escaneos: las tablas de puestos
y las estructuras de costos suelen pegarse como imagen.

**Motor de OCR.** PaddleOCR (sesion 10) cuando esta instalado, que es el caso del
pipeline en local (`uv sync --group ocr`). En Streamlit Community Cloud PaddlePaddle no
cabe en 1 GB de memoria, asi que se usa RapidOCR: corre los mismos modelos PP-OCR
convertidos a ONNX, sin instalar Paddle. El resultado registra que motor leyo cada
pagina.

**No se manda el PDF entero al LLM.** Se localizan los terminos de referencia (TDR)
puntuando cada pagina por palabras clave del servicio (puesto, turno, agente, arma...)
y se envian solo esas paginas, hasta `max_caracteres_llm`. Eso baja el costo por
proceso de ~60 mil tokens a ~4 mil.
"""

from __future__ import annotations

import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import Config, load_config
from .datos import normalizar
from .red import Cliente

log = logging.getLogger("garita.documentos")


@dataclass
class PaginaLeida:
    numero: int
    texto: str
    clase: str          # "texto" | "imagen"
    motor: str          # "capa_texto" | "paddleocr" | "rapidocr" | "sin_ocr"
    puntaje: float = 0.0


@dataclass
class DocumentoLeido:
    paginas_totales: int
    paginas: list[PaginaLeida] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(f"[p. {p.numero}]\n{p.texto}" for p in self.paginas if p.texto.strip())

    @property
    def paginas_ocr(self) -> int:
        return sum(p.motor in ("paddleocr", "rapidocr") for p in self.paginas)


# ===== HERRAMIENTA 10 · Document AI =====
# --- 10.1 Motor: PaddleOCR si esta instalado, RapidOCR (PP-OCR en ONNX) si no
_MOTOR: dict = {}


def motor_ocr():
    """Construye el motor una sola vez. Reconstruirlo por pagina recarga el modelo."""
    if "motor" in _MOTOR:
        return _MOTOR["motor"], _MOTOR["nombre"]
    try:
        from paddleocr import PaddleOCR

        _MOTOR["motor"] = PaddleOCR(lang="es", use_doc_orientation_classify=False,
                                    use_doc_unwarping=False, use_textline_orientation=False)
        _MOTOR["nombre"] = "paddleocr"
    except Exception:  # noqa: BLE001 - Paddle no instalado o sin memoria
        try:
            from rapidocr_onnxruntime import RapidOCR

            _MOTOR["motor"] = RapidOCR()
            _MOTOR["nombre"] = "rapidocr"
        except Exception:  # noqa: BLE001
            _MOTOR["motor"], _MOTOR["nombre"] = None, "sin_ocr"
    log.info("Motor de OCR: %s", _MOTOR["nombre"])
    return _MOTOR["motor"], _MOTOR["nombre"]


def ocr_imagen(png: bytes) -> tuple[str, str]:
    """Texto de una imagen de pagina. Devuelve (texto, motor usado)."""
    motor, nombre = motor_ocr()
    if motor is None:
        return "", "sin_ocr"
    import numpy as np
    import cv2

    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if nombre == "paddleocr":
        lineas = []
        for res in motor.predict(img):
            lineas += list(res.get("rec_texts", []))
        return "\n".join(lineas), nombre
    resultado, _ = motor(img)
    return "\n".join(r[1] for r in (resultado or [])), nombre


# --- 10.2 Triaje: clasifica cada pagina en texto o imagen
def triaje(pdf: bytes | Path, umbral: int) -> tuple[object, list[PaginaLeida]]:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    paginas = []
    for i, pag in enumerate(doc, start=1):
        t = pag.get_text()
        clase = "texto" if len(t.strip()) > umbral else "imagen"
        paginas.append(PaginaLeida(i, t if clase == "texto" else "", clase,
                                   "capa_texto" if clase == "texto" else "sin_ocr"))
    return doc, paginas


def _ocr_paginas(doc, paginas: list[PaginaLeida], numeros: list[int]) -> None:
    for n in numeros:
        pag = doc[n - 1]
        png = pag.get_pixmap(dpi=200).tobytes("png")
        texto, motor = ocr_imagen(png)
        paginas[n - 1].texto, paginas[n - 1].motor = texto, motor


# --- 10.3 Localizacion: puntua paginas y se queda con los terminos de referencia
def _puntuar(texto: str, palabras: list[str]) -> float:
    t = normalizar(texto)
    return float(sum(len(re.findall(rf"\b{normalizar(p)}\b", t)) for p in palabras))


def leer_tdr(pdf: bytes | Path, cfg: Config | None = None) -> DocumentoLeido:
    """
    Devuelve solo las paginas de terminos de referencia de unas Bases, ya leidas.

    1. Triaje de todas las paginas.
    2. Se puntua cada pagina con texto por palabras del servicio.
    3. La ventana de TDR es el bloque de `VENTANA` paginas seguidas con mayor puntaje
       total. No se busca el titulo "terminos de referencia": el OCR viejo de las Bases
       lo deforma ("TERMlNOS", "TÉRM|NOS") y la primera prueba eligio un anexo final.
    4. Las paginas imagen dentro de la ventana pasan por OCR (con tope) y se puntuan.
    5. Se envian las mejor puntuadas, en orden, hasta el limite de caracteres.
    """
    cfg = cfg or load_config()
    dc = cfg.documentos
    doc, paginas = triaje(pdf, int(dc["umbral_caracteres"]))
    n = len(paginas)
    for p in paginas:
        p.puntaje = _puntuar(p.texto, dc["palabras_tdr"])

    VENTANA = 14
    puntajes = [p.puntaje for p in paginas]
    sumas = [sum(puntajes[i:i + VENTANA]) for i in range(max(1, n - VENTANA + 1))]
    inicio = max(range(len(sumas)), key=lambda i: sumas[i]) + 1 if sumas else 1
    ventana = range(inicio, min(n, inicio + VENTANA - 1) + 1)

    imagen = [i for i in ventana if paginas[i - 1].clase == "imagen"][: int(dc["max_paginas_ocr"])]
    if imagen:
        _ocr_paginas(doc, paginas, imagen)
        for i in imagen:
            paginas[i - 1].puntaje = _puntuar(paginas[i - 1].texto, dc["palabras_tdr"]) + 1.0

    candidatas = sorted((paginas[i - 1] for i in ventana if paginas[i - 1].puntaje > 0),
                        key=lambda p: -p.puntaje)
    elegidas, total = [], 0
    for p in candidatas:
        if total + len(p.texto) > int(dc["max_caracteres_llm"]):
            continue
        elegidas.append(p)
        total += len(p.texto)
    elegidas.sort(key=lambda p: p.numero)
    return DocumentoLeido(paginas_totales=n, paginas=elegidas)


def leer_documento(pdf: bytes, cfg: Config | None = None, max_paginas: int = 6) -> DocumentoLeido:
    """Lee un documento corto que sube el usuario (carta fianza, poliza, resolucion)."""
    cfg = cfg or load_config()
    doc, paginas = triaje(pdf, int(cfg.documentos["umbral_caracteres"]))
    paginas = paginas[:max_paginas]
    _ocr_paginas(doc, paginas, [p.numero for p in paginas if p.clase == "imagen"])
    return DocumentoLeido(paginas_totales=len(doc), paginas=paginas)


# --- 10.4 Salida: descarga las Bases de cada proceso y guarda el texto de sus TDR
def _procesar_bases(cli: Cliente, cfg: Config, ocid: str, url: str) -> dict:
    destino = cfg.raw_dir / "bases" / f"{ocid}.pdf"
    try:
        cli.descargar(url, destino)
        d = leer_tdr(destino, cfg)
        return {"ocid": ocid, "paginas_totales": d.paginas_totales,
                "paginas_tdr": ",".join(str(p.numero) for p in d.paginas),
                "paginas_ocr": d.paginas_ocr,
                "motores": ",".join(sorted({p.motor for p in d.paginas})),
                "caracteres": len(d.texto), "texto_tdr": d.texto, "error": ""}
    except Exception as e:  # noqa: BLE001 - un PDF roto no corta el lote
        return {"ocid": ocid, "paginas_totales": 0, "paginas_tdr": "", "paginas_ocr": 0,
                "motores": "", "caracteres": 0, "texto_tdr": "", "error": str(e)[:200]}


def seleccionar_procesos(contratos: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Procesos que entran al benchmark: con contrato firmado, monto, plazo y Bases, y en
    los que todos los items terminaron en contrato (si un item quedo desierto, el monto
    firmado no corresponde a todos los puestos de las Bases).
    """
    c = contratos[contratos["con_contrato"] & contratos["url_bases"].notna()
                  & (contratos["duracion_dias"].fillna(0) >= 28)
                  & (contratos["n_contratos"].fillna(0) >= contratos["n_items"].clip(lower=1))]
    c = c.sort_values("fecha_firma", ascending=False)
    # Lima concentra dos tercios de los contratos. Para que el benchmark sirva en las
    # regiones mineras, entran primero todos los de provincia y Lima completa el cupo.
    tope = int(cfg.oece["max_procesos_llm"])
    provincia = c[c["departamento"] != "LIMA"].head(tope)
    lima = c[c["departamento"] == "LIMA"].head(max(tope - len(provincia), tope // 4))
    return pd.concat([provincia, lima]).head(tope + tope // 4)


def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    contratos = pd.read_parquet(cfg.processed_dir / "contratos_vigilancia.parquet")
    sel = seleccionar_procesos(contratos, cfg)
    destino = cfg.processed_dir / "tdr_textos.parquet"
    previos = pd.read_parquet(destino) if destino.exists() else pd.DataFrame(columns=["ocid", "error"])
    hechos = set(previos.loc[previos["error"].fillna("") == "", "ocid"])
    pendientes = sel[~sel["ocid"].isin(hechos)]
    log.info("Document AI: %d procesos elegidos, %d ya leidos, %d pendientes",
             len(sel), len(hechos), len(pendientes))
    motor_ocr()  # se construye antes de abrir los hilos
    cli = Cliente(cfg, espera=0.3)
    filas = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futuros = [ex.submit(_procesar_bases, cli, cfg, r.ocid, r.url_bases)
                   for r in pendientes.itertuples()]
        for i, f in enumerate(futuros, 1):
            filas.append(f.result())
            if i % 20 == 0 or i == len(futuros):
                log.info("  bases %d/%d", i, len(futuros))
    nuevos = pd.DataFrame(filas)
    tabla = pd.concat([previos[previos["ocid"].isin(hechos)], nuevos], ignore_index=True)
    tabla.to_parquet(destino, index=False)
    resumen = {"procesos": int(len(tabla)), "con_texto": int((tabla["caracteres"] > 500).sum()),
               "con_ocr": int((tabla["paginas_ocr"] > 0).sum()),
               "errores": int((tabla["error"].fillna("") != "").sum())}
    log.info("Document AI listo: %s", resumen)
    return resumen
