"""
Evaluacion de la extraccion: ¿el LLM lee las Bases mejor que unas reglas fijas?

    uv run python eval/evaluar_extraccion.py

No hay un conjunto etiquetado de puestos por contrato, asi que la evaluacion usa tres
medidas que no lo necesitan y una muestra para revision humana:

1. **Cobertura.** En cuantos procesos cada metodo encuentra un numero de puestos.
2. **Plausibilidad.** Con ese numero se calcula el precio por puesto-mes; un error de
   lectura (contar agentes como puestos, leer un numero de pagina) produce precios
   imposibles. Se mide que parte cae en el rango plausible [S/1,500; S/50,000].
3. **Consistencia.** Si la lectura es correcta, contratos parecidos tienen precios
   parecidos: se compara la dispersion relativa (rango intercuartil / mediana).
4. **Auditoria.** Una muestra aleatoria de 15 extracciones del LLM con su cita textual
   y el link a las Bases, en eval/resultados/auditoria_muestra.csv, para que una
   persona marque si el numero es correcto. La columna `correcto` empieza vacia.

La linea base son reglas que buscaria cualquiera: "N puestos", "N agentes" o
"N vigilantes" y "24 horas" / "12 horas" en el texto de los TDR.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garita.benchmark import DIAS_POR_MES, PRECIO_MAX, PRECIO_MIN  # noqa: E402
from garita.config import load_config  # noqa: E402
from garita.datos import normalizar  # noqa: E402


# ===== HERRAMIENTA 12 · Despliegue y evaluacion =====
# --- 12.1 Linea base: reglas fijas sobre el mismo texto que recibe el LLM
def linea_base(texto: str) -> tuple[float | None, int | None]:
    """Devuelve (puestos 24/7 equivalentes, horas) segun las reglas, o (None, None)."""
    t = normalizar(texto)
    puestos = [int(n) for n in re.findall(r"\b(\d{1,3})\s*\(?\w*\)?\s*PUESTOS?\b", t) if 0 < int(n) < 300]
    if not puestos:
        agentes = [int(n) for n in re.findall(r"\b(\d{1,3})\s*(?:AGENTES|VIGILANTES)\b", t) if 0 < int(n) < 600]
        if not agentes:
            return None, None
        horas = 24 if "24 HORAS" in t else 12 if "12 HORAS" in t else 24
        # Sin puestos explicitos, la regla asume que cada 3 agentes cubren un puesto 24/7.
        return max(agentes) / 3, horas
    horas = 24 if "24 HORAS" in t else 12 if "12 HORAS" in t else 24
    return float(max(puestos)) * horas / 24, horas


# --- 12.2 Metricas: cobertura, plausibilidad y dispersion de cada metodo
def metricas(precios: pd.Series) -> dict:
    v = precios.dropna()
    plaus = v[(v >= PRECIO_MIN) & (v <= PRECIO_MAX)]
    iqr = plaus.quantile(0.75) - plaus.quantile(0.25) if len(plaus) else None
    return {"con_puestos": int(len(v)),
            "plausibles": int(len(plaus)),
            "pct_plausible": round(100 * len(plaus) / len(v), 1) if len(v) else None,
            "mediana": round(plaus.median(), 0) if len(plaus) else None,
            "dispersion_iqr_sobre_mediana": round(iqr / plaus.median(), 3) if len(plaus) else None}


def main() -> None:
    cfg = load_config()
    p = cfg.processed_dir
    textos = pd.read_parquet(p / "tdr_textos.parquet")
    contratos = pd.read_parquet(p / "contratos_vigilancia.parquet")
    ext = pd.read_parquet(p / "extracciones_llm.parquet")
    d = (textos[textos["caracteres"] > 500][["ocid", "texto_tdr"]]
         .merge(contratos[["ocid", "monto_contrato", "duracion_dias", "url_bases", "entidad"]], on="ocid")
         .merge(ext[["ocid", "puestos_equivalentes_24h", "confianza", "evidencia", "n_puestos"]],
                on="ocid", how="left"))
    d["meses"] = d["duracion_dias"] / DIAS_POR_MES
    base = d["texto_tdr"].map(linea_base)
    d["base_equiv"] = [b[0] for b in base]
    d["precio_base"] = d["monto_contrato"] / (d["base_equiv"] * d["meses"])
    d["llm_equiv"] = d["puestos_equivalentes_24h"].where(d["puestos_equivalentes_24h"] > 0)
    d["precio_llm"] = d["monto_contrato"] / (d["llm_equiv"] * d["meses"])

    # --- 12.3 Resultado: tabla comparativa y muestra para auditoria humana
    res = pd.DataFrame([{"metodo": "Linea base (reglas)", **metricas(d["precio_base"])},
                        {"metodo": "LLM (deepseek-chat + Pydantic)", **metricas(d["precio_llm"])}])
    res.insert(1, "procesos_evaluados", len(d))
    salida = cfg.root / "eval" / "resultados"
    salida.mkdir(parents=True, exist_ok=True)
    res.to_csv(salida / "llm_vs_linea_base.csv", index=False)
    ambos = d.dropna(subset=["base_equiv", "llm_equiv"])
    acuerdo = (abs(ambos["base_equiv"] - ambos["llm_equiv"]) <= 0.5).mean() if len(ambos) else None
    print(res.to_string(index=False))
    print(f"\nAcuerdo exacto (+-0.5 puestos) donde ambos encuentran puestos: "
          f"{acuerdo:.0%} de {len(ambos)}" if acuerdo is not None else "")

    muestra = d.dropna(subset=["llm_equiv"]).sample(min(15, d["llm_equiv"].notna().sum()), random_state=20261118)
    muestra.assign(correcto="", comentario="")[
        ["ocid", "entidad", "n_puestos", "llm_equiv", "base_equiv", "confianza", "evidencia", "url_bases",
         "correcto", "comentario"]].to_csv(salida / "auditoria_muestra.csv", index=False, encoding="utf-8-sig")
    print(f"Muestra para auditoria: {salida / 'auditoria_muestra.csv'}")


if __name__ == "__main__":
    main()
