"""
Crea los documentos SINTETICOS del demo en data/demo/.

Una carta fianza ficticia en dos versiones: con capa de texto (se lee directo) y
escaneada (solo imagen, obliga a pasar por OCR). Banco, empresa y beneficiario son
inventados y el documento dice SINTETICO en el encabezado: nunca se presenta como real.

    uv run python scripts/crear_documentos_demo.py
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parent.parent
DEMO = RAIZ / "data" / "demo"

TEXTO = """DOCUMENTO SINTETICO PARA DEMO - NO ES UN DOCUMENTO REAL

BANCO EJEMPLO DEL PERU S.A. (entidad ficticia)
CARTA FIANZA N.° 0099-2026-DEMO

Lima, 15/11/2026

Senores
MINERA ANDINA DEMO S.A.C. (beneficiario ficticio)
Presente.-

Por la presente, y a solicitud de nuestro cliente SEGURIDAD INTEGRAL DEMO S.A.C.,
RUC 20999999991 (empresa ficticia), otorgamos a favor de ustedes una fianza solidaria,
irrevocable, incondicional y de realizacion automatica, hasta por la suma de
S/ 96,000.00 (noventa y seis mil y 00/100 soles), para garantizar el fiel
cumplimiento del contrato de servicio de vigilancia privada con armas en el
campamento minero ubicado en la provincia de Pataz, La Libertad.

La presente carta fianza tiene vigencia desde el 15/11/2026 hasta el 14/02/2027.

Atentamente,
Area de Cartas Fianza - Banco Ejemplo del Peru S.A.
"""


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    pag = doc.new_page(width=595, height=842)
    pag.insert_textbox(pymupdf.Rect(60, 60, 540, 800), TEXTO, fontsize=11, fontname="helv")
    pag.draw_rect(pymupdf.Rect(50, 50, 545, 82), color=(0.8, 0.1, 0.1), width=1.2)
    con_texto = DEMO / "carta_fianza_sintetica.pdf"
    doc.save(con_texto)

    # Version escaneada: la pagina se rasteriza y se pega como imagen, sin capa de texto.
    img = pag.get_pixmap(dpi=150)
    esc = pymupdf.open()
    p2 = esc.new_page(width=595, height=842)
    p2.insert_image(p2.rect, pixmap=img)
    escaneada = DEMO / "carta_fianza_sintetica_escaneada.pdf"
    esc.save(escaneada)
    print("Creados:", con_texto.name, escaneada.name)


if __name__ == "__main__":
    main()
