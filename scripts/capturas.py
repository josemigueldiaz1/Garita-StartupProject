"""
Toma las 3 capturas del README con la app corriendo en local.

    uv run streamlit run app.py --server.headless true      # en otra terminal
    uv run --with playwright python scripts/capturas.py

Abre la app en un navegador sin ventana, recorre las pestanas del flujo del demo y
guarda docs/capturas/1_riesgo.png, 2_proveedores.png y 3_precio.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "capturas"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"

PESTANAS = [("2 · Riesgo de la zona", "1_riesgo.png"),
            ("3 · Proveedores", "2_proveedores.png"),
            ("4 · Precio", "3_precio.png")]


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        pag.goto(URL, wait_until="networkidle")
        pag.get_by_text("Contrata seguridad privada").wait_for(timeout=60000)
        pag.wait_for_timeout(3000)
        for nombre, archivo in PESTANAS:
            pag.get_by_role("tab", name=nombre).click()
            pag.wait_for_timeout(6000)
            pag.screenshot(path=str(SALIDA / archivo), full_page=False)
            print("captura:", archivo)
        nav.close()


if __name__ == "__main__":
    main()
