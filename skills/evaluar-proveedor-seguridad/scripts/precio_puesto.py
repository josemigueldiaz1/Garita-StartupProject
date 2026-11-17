"""
precio_puesto.py — la aritmetica de una oferta de seguridad, para la skill del producto.

    uv run python skills/evaluar-proveedor-seguridad/scripts/precio_puesto.py \
        --monto 950000 --puestos-24h 8 --meses 12 --departamento "La Libertad"

Tres usos, segun lo que se le pase:

1. **Normalizar una propuesta** (--monto con puestos y meses): monto total -> soles por
   puesto 24/7 equivalente y mes, y su semaforo frente al piso legal y al mercado.
2. **Evaluar un precio ya unitario** (--precio-ofertado y --horas-dia).
3. **Estimar el pedido** (solo puestos y meses): cuanto deberia costar segun el rango
   de mercado del departamento.

La skill lo corre en vez de pedirle la cuenta al modelo: una division hecha por el
modelo puede salir mal y no deja rastro; esta sale igual cada vez e imprime de donde
viene cada numero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ===== HERRAMIENTA 16 · Skills de Claude Code =====
# --- 16.1 Arranque: el script vive en skills/<skill>/scripts/; la raiz del repo esta 3 niveles arriba
RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from garita import benchmark as bm  # noqa: E402
from garita import datos  # noqa: E402
from garita.config import load_config  # noqa: E402


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Precio por puesto-mes y semaforo de una oferta de seguridad.")
    p.add_argument("--monto", type=float, help="monto total de la oferta o contrato, en soles")
    p.add_argument("--puestos-24h", type=float, default=0, help="puestos de 24 horas")
    p.add_argument("--puestos-12h", type=float, default=0, help="puestos de 12 horas")
    p.add_argument("--meses", type=float, help="duracion del servicio en meses")
    p.add_argument("--departamento", help="departamento del servicio, para el rango de mercado")
    p.add_argument("--precio-ofertado", type=float, help="precio por puesto y mes que ofrece la empresa")
    p.add_argument("--horas-dia", type=int, default=24, help="horas del puesto del precio ofertado")
    return p.parse_args()


# --- 16.2 Calculo: delega en garita/benchmark.py, el mismo codigo de la app y del MCP
def calcular(a: argparse.Namespace) -> dict:
    cfg = load_config()
    salida: dict = {"entrada": {k: v for k, v in vars(a).items() if v not in (None, 0)}}

    hay_benchmark = not datos.tabla("benchmark_departamento").empty
    b = datos.benchmark(a.departamento) if hay_benchmark else {}
    # numpy -> tipos de Python, para que el JSON muestre 5 y no "5"
    b = {k: (v.item() if hasattr(v, "item") else v) for k, v in b.items()}
    salida["mercado"] = (
        {k: (round(v, 2) if isinstance(v, float) else v) for k, v in b.items()} | {
            "nivel": "extraido", "fuente": cfg.oece["api_base"]}
        if b else {"mensaje": "Sin benchmark procesado: corre el paso benchmark del pipeline."})

    piso24 = bm.costo_laboral_minimo(24, cfg=cfg)
    salida["piso_legal_24h"] = {"soles_puesto_mes": piso24.piso_puesto_mes,
                                "agentes_por_puesto": piso24.agentes_necesarios,
                                "nivel": "calculado con la RMV verificada",
                                "fuente": cfg.costo_laboral["rmv_fuente"]}

    equivalentes = bm.puestos_equivalentes_24h(n_24h=a.puestos_24h, n_12h=a.puestos_12h)
    salida["puestos_24h_equivalentes"] = equivalentes

    if a.monto:
        precio = bm.precio_puesto_mes(a.monto, equivalentes, a.meses)
        if precio is None:
            salida["error"] = "Para normalizar un monto hacen falta puestos (--puestos-24h o --puestos-12h) y --meses."
        else:
            salida["oferta_normalizada"] = {"precio_puesto_mes": precio,
                                            **bm.evaluar_oferta(precio, 24, benchmark=b or None, cfg=cfg),
                                            "nivel": "declarado (monto de la oferta)"}

    if a.precio_ofertado:
        salida["oferta_unitaria"] = {**bm.evaluar_oferta(a.precio_ofertado, a.horas_dia,
                                                         benchmark=b or None, cfg=cfg),
                                     "horas_dia": a.horas_dia, "nivel": "declarado"}

    # --- 16.3 Estimacion: rango de mercado aplicado al pedido, con el piso como minimo
    if equivalentes and a.meses and b:
        factor = equivalentes * a.meses
        salida["estimado_pedido"] = {
            "minimo_legal": round(piso24.piso_puesto_mes * factor, 2),
            "p25": round(b["p25"] * factor, 2),
            "mediana": round(b["mediana"] * factor, 2),
            "p75": round(b["p75"] * factor, 2),
            "unidad": f"soles por {a.meses:g} meses",
            "alcance": b.get("alcance"),
        }
    return salida


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(calcular(_argumentos()), ensure_ascii=False, indent=2, default=str))
