"""
resumen_benchmark.py — el estado del benchmark y lo que costo construirlo.

    uv run python .claude/skills/regenerar-benchmark/scripts/resumen_benchmark.py
    uv run python .claude/skills/regenerar-benchmark/scripts/resumen_benchmark.py --solo-costos

Lee data/processed y logs/costos.csv; no llama a ninguna API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# ===== HERRAMIENTA 16 · Skills de Claude Code =====
# --- 16.1 Arranque: la raiz del repo esta 4 niveles arriba (.claude/skills/<skill>/scripts)
RAIZ = Path(__file__).resolve().parents[4]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from garita.config import load_config  # noqa: E402


# --- 16.4 Resumen: costos del LLM por franja y estado del benchmark
def costos(cfg) -> None:
    ruta = cfg.root / cfg.costos["archivo_log"]
    if not ruta.exists():
        print("Costos: aun no hay llamadas registradas en", ruta.relative_to(cfg.root))
        return
    df = pd.read_csv(ruta)
    if df.empty:
        print("Costos: el log esta vacio.")
        return
    print(f"Costos del LLM: {len(df)} llamadas, {int(df['exito'].sum())} exitosas, "
          f"US${df['costo_usd'].sum():.4f} en total (tope {cfg.tope_usd():.2f})")
    print(df.groupby("franja")["costo_usd"].agg(["count", "sum"]).round(4).to_string())


def benchmark(cfg) -> None:
    proc = cfg.processed_dir
    contratos = proc / "benchmark_contratos.parquet"
    deptos = proc / "benchmark_departamento.parquet"
    if not contratos.exists() or not deptos.exists():
        print("Benchmark: falta correr el paso benchmark.")
        return
    c = pd.read_parquet(contratos)
    validos = int(c["valido"].sum()) if "valido" in c else len(c)
    print(f"\nContratos: {len(c)} leidos, {validos} validos para el benchmark")
    if "motivo_exclusion" in c:
        motivos = c.loc[~c["valido"], "motivo_exclusion"].value_counts()
        if len(motivos):
            print("Excluidos por motivo:\n" + motivos.to_string())
    d = pd.read_parquet(deptos).sort_values("n", ascending=False)
    print("\nSoles por puesto 24/7 y mes, por departamento:")
    print(d.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--solo-costos", action="store_true")
    a = p.parse_args()
    cfg = load_config()
    costos(cfg)
    if not a.solo_costos:
        benchmark(cfg)
