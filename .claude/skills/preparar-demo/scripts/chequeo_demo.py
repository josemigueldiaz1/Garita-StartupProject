"""
chequeo_demo.py — todo lo que tiene que estar en pie antes de presentar Garita.

    uv run python .claude/skills/preparar-demo/scripts/chequeo_demo.py
    uv run python .claude/skills/preparar-demo/scripts/chequeo_demo.py --sin-pruebas

Revisa, sin llamar a ninguna API ni gastar tokens:

1. Que las tablas de data/processed existan y no esten vacias. Las criticas son las
   que usa el flujo del demo; si una falta, la app no puede mostrar ese paso.
2. Las fechas de corte de cada fuente (metadatos.json), para decirlas en vivo.
3. Si la clave de DeepSeek esta cargada: solo si o no, nunca su valor.
4. El caso del demo de punta a punta: vigilancia con armas, 8 puestos 24/7, Pataz.
5. Las pruebas (pytest).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

# ===== HERRAMIENTA 16 · Skills de Claude Code =====
# --- 16.1 Arranque: la raiz del repo esta 4 niveles arriba (.claude/skills/<skill>/scripts)
RAIZ = Path(__file__).resolve().parents[4]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from garita import benchmark as bm  # noqa: E402
from garita import datos  # noqa: E402
from garita.config import Config, load_config  # noqa: E402

# Tabla -> True si el flujo del demo no funciona sin ella.
TABLAS = {
    "sucamec_resoluciones": True,
    "empresas": False,
    "contratos_vigilancia": False,
    "extracciones_llm": False,
    "benchmark_contratos": True,
    "benchmark_departamento": True,
    "proveedores_oece": False,
    "experiencia_publica": False,
    "sunat_ruc": False,
    "conflictos": False,
    "conflictos_provincia": True,
}
CASO = {"departamento": "LA LIBERTAD", "provincia": "PATAZ", "armas": "CON ARMAS",
        "puestos_24h": 8, "meses": 12}


# --- 16.7 Chequeos: tablas, fechas, clave, caso del demo y pruebas
def chequear_tablas(proc: Path) -> int:
    criticas_faltantes = 0
    print("Tablas en data/processed:")
    for nombre, critica in TABLAS.items():
        ruta = proc / f"{nombre}.parquet"
        filas = len(pd.read_parquet(ruta)) if ruta.exists() else 0
        ok = filas > 0
        if not ok and critica:
            criticas_faltantes += 1
        marca = "OK    " if ok else ("FALTA " if critica else "aviso ")
        print(f"  {marca} {nombre:<24} {filas:>7,} filas")
    for extra, critica in (("provincias.geojson", True), ("metadatos.json", False)):
        existe = (proc / extra).exists()
        if not existe and critica:
            criticas_faltantes += 1
        print(f"  {'OK    ' if existe else ('FALTA ' if critica else 'aviso ')} {extra}")
    return criticas_faltantes


def fechas_de_corte(proc: Path) -> None:
    ruta = proc / "metadatos.json"
    if not ruta.exists():
        print("\nFechas de corte: falta metadatos.json (paso metadatos del pipeline).")
        return
    meta = json.loads(ruta.read_text(encoding="utf-8"))
    print("\nFechas de corte por fuente:")
    for fuente, info in meta.items():
        if isinstance(info, dict):
            fecha = info.get("fecha_corte") or info.get("fecha") or info.get("reporte") or ""
            print(f"  {fuente:<14} {fecha}")


def caso_del_demo() -> bool:
    c = CASO
    print(f"\nCaso del demo: vigilancia {c['armas'].lower()}, {c['puestos_24h']} puestos 24/7, "
          f"campamento en {c['provincia'].title()} ({c['departamento'].title()})")
    if datos.tabla("sucamec_resoluciones").empty:
        print("  FALTA  sin datos de SUCAMEC")
        return False
    empresas = datos.buscar_empresas(c["departamento"], armas=c["armas"], provincia=c["provincia"])
    en_prov = int(empresas["sede_en_provincia"].sum()) if not empresas.empty else 0
    print(f"  {'OK   ' if len(empresas) else 'FALTA'}  {len(empresas)} empresas autorizadas con armas "
          f"en el departamento ({en_prov} con sede en la provincia)")
    b = datos.benchmark(c["departamento"]) if not datos.tabla("benchmark_departamento").empty else {}
    if b:
        print(f"  OK     benchmark {b.get('alcance')}: mediana S/ {b['mediana']:,.0f} por puesto-mes (n={int(b['n'])})")
    else:
        print("  FALTA  sin benchmark")
    piso = bm.costo_laboral_minimo(24).piso_puesto_mes
    print(f"  OK     piso legal de un puesto 24/7: S/ {piso:,.0f} por mes")
    r = datos.riesgo_zona(c["departamento"], c["provincia"])
    if "casos_provincia" in r:
        print(f"  OK     riesgo: {r['casos_provincia']} casos en la provincia, "
              f"{r.get('conflictos_departamento', 0)} conflictos en el departamento, "
              f"{len(r.get('estados_emergencia', []))} estados de emergencia")
    else:
        print("  FALTA  sin datos de conflictos")
    return bool(len(empresas)) and bool(b) and "casos_provincia" in r


def correr_pruebas() -> bool:
    print("\nPruebas:")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ultima = (r.stdout.strip().splitlines() or ["sin salida"])[-1]
    print(f"  {'OK   ' if r.returncode == 0 else 'FALLA'}  {ultima}")
    return r.returncode == 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sin-pruebas", action="store_true")
    a = p.parse_args()
    cfg = load_config()

    faltan = chequear_tablas(cfg.processed_dir)
    fechas_de_corte(cfg.processed_dir)
    clave = Config.estado_credenciales()["DEEPSEEK_API_KEY"]
    print(f"\nClave de DeepSeek cargada: {'si' if clave else 'no (la app corre en modo demo)'}")
    caso_ok = caso_del_demo()
    pruebas_ok = True if a.sin_pruebas else correr_pruebas()

    print("\nPara presentar:")
    print("  uv run streamlit run app.py        (y abrir tambien la URL publica)")
    print("  guion: docs/guion_demo.md · conectarse 7:25 a. m. con el demo abierto y probado")
    print("  video de respaldo listo por si se cae internet")

    listo = faltan == 0 and caso_ok and pruebas_ok and (RAIZ / "app.py").exists()
    if not (RAIZ / "app.py").exists():
        print("\nFALTA  app.py")
    print("\nResultado:", "LISTO para el demo" if listo else "NO listo: revisa las lineas FALTA o FALLA")
    return 0 if listo else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
