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


def _ocr_paginas(doc, paginas: list[PaginaLeida], numeros: list[int], dpi: int = 200) -> None:
    for n in numeros:
        pag = doc[n - 1]
        png = pag.get_pixmap(dpi=dpi).tobytes("png")
        texto, motor = ocr_imagen(png)
        paginas[n - 1].texto, paginas[n - 1].motor = texto, motor


# --- 10.3 Localizacion: puntua paginas y se queda con los terminos de referencia
# Lo que delata la tabla de dimensionamiento del servicio (suma) y lo que delata las
# secciones que tambien hablan de "puestos" y "agentes" pero no sirven (resta): las
# penalidades ("por cada puesto no cubierto"), los factores de evaluacion y las clausulas.
# La primera version contaba palabras sueltas y elegia esas secciones en 127 de 161 casos.
SENALES_TDR = [(r"\bPUESTOS?\b", 4), (r"\b(?:24|12|8|08)\s*HORAS\b", 3), (r"\b(?:DIURNO|NOCTURNO)S?\b", 2),
               (r"\b\d{1,2}[:.]\d{2}\b", 1), (r"\bTURNOS?\b", 1), (r"LUNES A (?:DOMINGO|SABADO)", 2),
               (r"\b(?:VIGILANTES?|AGENTES?)\b", 1), (r"\bCANTIDAD\b", 2), (r"\bSEDES?\b", 2),
               (r"DIMENSIONAMIENTO|DISTRIBUCION DE(?:L)? (?:PERSONAL|PUESTOS)|RELACION DE PUESTOS", 4)]
SENALES_RUIDO = [(r"\bPENALIDAD(?:ES)?\b", 3), (r"FACTOR(?:ES)? DE EVALUACION", 3), (r"\bCLAUSULA\b", 2),
                 (r"\bGARANTIAS?\b", 2), (r"EXPERIENCIA DEL POSTOR", 3), (r"\bARBITRA", 2)]


def _puntuar(texto: str, palabras: list[str] | None = None) -> float:
    t = normalizar(texto)
    mas = sum(w * len(re.findall(p, t)) for p, w in SENALES_TDR)
    menos = sum(w * len(re.findall(p, t)) for p, w in SENALES_RUIDO)
    return float(max(mas - menos, 0))


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

    # Bases escaneadas: si la mitad o mas son imagen, no hay texto con que ubicar los
    # TDR. Pasada rapida de OCR a 110 dpi sobre una de cada tres paginas imagen del
    # tramo 20%-95% (los TDR nunca estan en la portada ni en los anexos finales) para
    # puntuarlas; despues, OCR fino solo dentro de la ventana elegida.
    escaneado = sum(p.clase == "imagen" for p in paginas) >= 0.5 * n
    if escaneado:
        muestra = [p.numero for p in paginas[int(n * 0.2):int(n * 0.95)] if p.clase == "imagen"][::3]
        _ocr_paginas(doc, paginas, muestra, dpi=110)
        for i in muestra:
            paginas[i - 1].puntaje = _puntuar(paginas[i - 1].texto, dc["palabras_tdr"])
            # El vecino sin muestrear hereda el puntaje para que la ventana lo incluya.
            for v in (i - 1, i + 1):
                if 1 <= v <= n and paginas[v - 1].clase == "imagen" and not paginas[v - 1].texto:
                    paginas[v - 1].puntaje = max(paginas[v - 1].puntaje, paginas[i - 1].puntaje * 0.8)

    VENTANA = 14
    puntajes = [p.puntaje for p in paginas]
    sumas = [sum(puntajes[i:i + VENTANA]) for i in range(max(1, n - VENTANA + 1))]
    inicio = max(range(len(sumas)), key=lambda i: sumas[i]) + 1 if sumas else 1
    ventana = range(inicio, min(n, inicio + VENTANA - 1) + 1)

    tope_ocr = int(dc["max_paginas_ocr"]) + (4 if escaneado else 0)
    imagen = sorted((i for i in ventana if paginas[i - 1].clase == "imagen"),
                    key=lambda i: -paginas[i - 1].puntaje)[:tope_ocr]
    if imagen:
        _ocr_paginas(doc, paginas, imagen)
        for i in imagen:
            paginas[i - 1].puntaje = _puntuar(paginas[i - 1].texto, dc["palabras_tdr"]) + 1.0

    # Re-OCR de las paginas clave aunque tengan capa de texto. Muchas Bases traen un OCR
    # antiguo ilegible justo en la tabla de puestos ("CANTIDAD DE AGENTES POR TURNO" sin
    # numeros legibles, segun el propio LLM). Se pasan por RapidOCR las 3 mejor puntuadas
    # y su pagina siguiente, y se queda la version que mejor puntua.
    top = sorted((p for p in paginas if p.puntaje > 0), key=lambda p: -p.puntaje)[:3]
    clave = sorted({q for p in top for q in (p.numero, p.numero + 1) if q <= n})[:6]
    for i in clave:
        p = paginas[i - 1]
        if p.motor in ("paddleocr", "rapidocr"):
            continue
        original, motor_original = p.texto, p.motor
        _ocr_paginas(doc, paginas, [i])
        nuevo = _puntuar(p.texto)
        if nuevo >= _puntuar(original) and p.texto.strip():
            p.puntaje = nuevo + 0.5
        else:
            p.texto, p.motor = original, motor_original

    # Candidatas de TODO el documento, no solo de la ventana: la tabla de puestos a veces
    # esta en un anexo lejos del resto de los TDR. La mejor pagina entra con sus vecinas,
    # porque las tablas suelen continuar en la pagina siguiente.
    candidatas = sorted((p for p in paginas if p.puntaje > 0), key=lambda p: -p.puntaje)
    if candidatas:
        mejor = candidatas[0].numero
        vecinas = [paginas[v - 1] for v in (mejor - 1, mejor + 1) if 1 <= v <= n and paginas[v - 1].texto]
        candidatas = [candidatas[0]] + vecinas + [p for p in candidatas[1:] if p not in vecinas]
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
def _pdf_desde_zip(contenido: bytes) -> bytes:
    """
    SEACE publica una cuarta parte de las Bases comprimidas. Del ZIP se toma el PDF cuyo
    nombre dice "bases" (o "integradas"); si ninguno lo dice, el mas grande. Los RAR y 7z
    necesitan herramientas externas y quedan fuera, con su error registrado.
    """
    import zipfile

    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        pdfs = [i for i in zf.infolist() if i.filename.lower().endswith(".pdf")]
        if not pdfs:
            raise ValueError("ZIP sin PDF")
        nombrados = [i for i in pdfs if re.search(r"(?i)bases|integrad", i.filename)]
        elegido = max(nombrados or pdfs, key=lambda i: i.file_size)
        return zf.read(elegido)


def _procesar_bases(cli: Cliente, cfg: Config, ocid: str, url: str) -> dict:
    destino = cfg.raw_dir / "bases" / f"{ocid}.pdf"
    try:
        cli.descargar(url, destino)
        contenido = destino.read_bytes()
        if contenido[:2] == b"PK":
            contenido = _pdf_desde_zip(contenido)
        elif contenido[:4] in (b"Rar!", b"7z\xbc\xaf"):
            raise ValueError("Bases en RAR/7z: formato no soportado")
        d = leer_tdr(contenido, cfg)
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


MIN_CARACTERES_TDR = 3000


def ejecutar(cfg: Config | None = None, releer_cortos: bool = False, releer_todo: bool = False,
             releer: set[str] | None = None) -> dict:
    """
    Lee las Bases de los procesos elegidos. Con `releer_cortos=True` vuelve a leer los que
    quedaron con menos de MIN_CARACTERES_TDR (casi siempre Bases escaneadas, que ahora
    pasan por la lectura con muestreo de OCR de `leer_tdr`). Con `releer_todo=True` relee
    todo desde los PDF ya descargados (sirve cuando cambia la regla de seleccion).
    """
    cfg = cfg or load_config()
    contratos = pd.read_parquet(cfg.processed_dir / "contratos_vigilancia.parquet")
    sel = seleccionar_procesos(contratos, cfg)
    destino = cfg.processed_dir / "tdr_textos.parquet"
    previos = pd.read_parquet(destino) if destino.exists() else pd.DataFrame(
        columns=["ocid", "error", "caracteres"])
    ok = previos["error"].fillna("") == ""
    if releer_cortos:
        ok &= previos["caracteres"].fillna(0) >= MIN_CARACTERES_TDR
    hechos = set() if releer_todo else set(previos.loc[ok, "ocid"]) - set(releer or ())
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
