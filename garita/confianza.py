"""
Puntaje de confianza de 0 a 100 de una empresa de seguridad, con su desglose.

El numero solo no sirve para decidir: un 70 puede ser una empresa impecable sin
experiencia publica o una con experiencia pero con penalidades. Por eso la funcion
devuelve cada componente con sus puntos, su maximo, el nivel del dato (verificado o
sin dato) y el link a la fuente, y la app pinta el desglose, no solo el total.

Los pesos estan en config.yaml -> confianza.pesos. Las reglas de cada componente son
deliberadamente simples y estan escritas aqui para que un comprador pueda auditarlas.

Lo que NO entra al puntaje porque no hay fuente publica: deuda coactiva y centrales
de riesgo (de pago), sanciones de SUCAMEC y de SUNAFIL. La app lo muestra como
"integracion futura" y nunca lo rellena con un supuesto.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .config import load_config
from .datos import buscar_empresas, normalizar, tabla

URL_SUCAMEC = "https://www.sucamec.gob.pe/rgGSSP/aplicacion/resoluciones/List.xhtml"
URL_SUNAT = "https://www.sunat.gob.pe/descargaPRR/padron_reducido_ruc.zip"
URL_OCDS = "https://contratacionesabiertas.oece.gob.pe"


def _comp(nombre, puntos, maximo, nivel, detalle, fuente):
    return {"nombre": nombre, "puntos": round(float(puntos), 1), "maximo": maximo,
            "nivel": nivel, "detalle": detalle, "fuente": fuente}


def _fila(nombre: str, ruc: str) -> dict | None:
    t = tabla(nombre)
    if t.empty or "ruc" not in t:
        return None
    f = t[t["ruc"] == ruc]
    return None if f.empty else f.iloc[0].to_dict()


def puntaje_confianza(ruc: str, departamento: str, modalidad: str = "VIGILANCIA PRIVADA",
                      armas: str | None = None) -> dict:
    cfg = load_config()
    w = cfg.confianza["pesos"]
    ruc, dep, mod = str(ruc), normalizar(departamento), normalizar(modalidad)
    res = tabla("sucamec_resoluciones")
    propias = res[(res["ruc"] == ruc) & res["vigente"]] if not res.empty else res
    razon = propias["razon_social"].iloc[0] if not propias.empty else (
        (_fila("sunat_ruc", ruc) or {}).get("razon_social_sunat", ""))
    comps = []

    # 1. Autorizacion SUCAMEC para la modalidad, en el departamento y con armas si se pide
    en_mod = propias[propias["modalidad"] == mod] if not propias.empty else propias
    en_dep = en_mod[en_mod["departamento"] == dep] if not en_mod.empty else en_mod
    pide_armas = armas and normalizar(armas) == "CON ARMAS"
    if pide_armas and not en_dep.empty:
        en_dep = en_dep[en_dep["armas"] == "CON ARMAS"]
    if not en_dep.empty:
        detalle = (f"Autorizada para {mod.lower()}{' con armas' if pide_armas else ''} con sede en "
                   f"{dep.title()} (resolucion {en_dep['resolucion'].iloc[0]}).")
        comps.append(_comp("Autorizacion SUCAMEC", w["autorizacion_sucamec"], w["autorizacion_sucamec"],
                           "verificado", detalle, URL_SUCAMEC))
    elif not en_mod.empty:
        comps.append(_comp("Autorizacion SUCAMEC", w["autorizacion_sucamec"] / 3, w["autorizacion_sucamec"],
                           "verificado", f"Autorizada para {mod.lower()} pero sin sede autorizada en "
                           f"{dep.title()}{' o sin armas' if pide_armas else ''}.", URL_SUCAMEC))
    else:
        comps.append(_comp("Autorizacion SUCAMEC", 0, w["autorizacion_sucamec"], "verificado",
                           f"No tiene autorizacion vigente para {mod.lower()}. Descartar.", URL_SUCAMEC))

    # 2. Meses hasta el vencimiento de la autorizacion relevante
    base = en_dep if not en_dep.empty else en_mod
    if not base.empty:
        vence = pd.to_datetime(base["fecha_vencimiento"]).min().date()
        meses = (vence - date.today()).days / 30.4
        pts = (w["vigencia_restante"] if meses >= 24 else 0.7 * w["vigencia_restante"] if meses >= 12
               else 0.4 * w["vigencia_restante"] if meses >= 6 else 0.1 * w["vigencia_restante"])
        comps.append(_comp("Vigencia de la autorizacion", pts, w["vigencia_restante"], "verificado",
                           f"Vence el {vence:%d/%m/%Y} ({meses:.0f} meses).", URL_SUCAMEC))
    else:
        comps.append(_comp("Vigencia de la autorizacion", 0, w["vigencia_restante"], "sin_dato",
                           "Sin autorizacion relevante.", URL_SUCAMEC))

    # 3. SUNAT: estado y condicion del RUC
    s = _fila("sunat_ruc", ruc)
    if s:
        ok = s["estado"] == "ACTIVO" and s["condicion"] == "HABIDO"
        pts = w["sunat"] if ok else (w["sunat"] / 3 if s["estado"] == "ACTIVO" else 0)
        comps.append(_comp("SUNAT", pts, w["sunat"], "verificado",
                           f"RUC {s['estado'].lower()}, {s['condicion'].lower()}.", URL_SUNAT))
    else:
        comps.append(_comp("SUNAT", 0, w["sunat"], "sin_dato", "RUC no encontrado en el padron.", URL_SUNAT))

    # 4 y 5. OECE: apto para contratar con el Estado y penalidades
    o = _fila("proveedores_oece", ruc)
    url_ficha = cfg.oece["ficha_publica"].format(ruc=ruc)
    if o and o.get("en_registro"):
        apto = o.get("apto_contratar")
        comps.append(_comp("Habilitada para contratar con el Estado", w["apto_estado"] if apto else 0,
                           w["apto_estado"], "verificado",
                           "Apta para contratar." if apto else "Inhabilitada o suspendida por el Tribunal.",
                           url_ficha))
        n = int(o.get("n_penalidades") or 0)
        pts = (w["penalidades"] if n == 0 else 0.6 * w["penalidades"] if n <= 2
               else 0.3 * w["penalidades"] if n <= 5 else 0)
        san = int(o.get("n_sanciones") or 0)
        comps.append(_comp("Penalidades y sanciones", pts if san == 0 else 0, w["penalidades"], "verificado",
                           f"{n} penalidades en contratos publicos; {san} sanciones del Tribunal.", url_ficha))
    else:
        comps.append(_comp("Habilitada para contratar con el Estado", w["apto_estado"] / 2, w["apto_estado"],
                           "sin_dato", "No figura en el registro de proveedores del Estado.", url_ficha))
        comps.append(_comp("Penalidades y sanciones", w["penalidades"] / 2, w["penalidades"], "sin_dato",
                           "Sin historial de contratos publicos para evaluar.", url_ficha))

    # 6. Experiencia en contratos publicos de vigilancia (12 meses de OCDS)
    e = _fila("experiencia_publica", ruc)
    n = int(e["n_contratos"]) if e else 0
    pts = (w["experiencia_publica"] if n >= 5 else 0.67 * w["experiencia_publica"] if n >= 2
           else 0.4 * w["experiencia_publica"] if n == 1 else 0)
    detalle = (f"{n} contratos de vigilancia con el Estado en 12 meses, por S/ {e['monto_total']:,.0f}."
               if e else "Sin contratos publicos de vigilancia en los ultimos 12 meses.")
    comps.append(_comp("Experiencia publica", pts, w["experiencia_publica"], "verificado", detalle, URL_OCDS))

    # 7. Cobertura territorial
    n_dep = propias["departamento"].nunique() if not propias.empty else 0
    pts = w["cobertura"] if n_dep >= 5 else 0.6 * w["cobertura"] if n_dep >= 2 else 0.2 * w["cobertura"] if n_dep else 0
    comps.append(_comp("Cobertura", pts, w["cobertura"], "verificado",
                       f"Sedes autorizadas en {n_dep} departamento(s).", URL_SUCAMEC))

    return {"ruc": ruc, "razon_social": razon, "puntaje": round(sum(c["puntos"] for c in comps)),
            "componentes": comps,
            "pendientes": ["Deuda coactiva SUNAT y centrales de riesgo (de pago): integracion futura",
                           "Sanciones de SUCAMEC y SUNAFIL: sin descarga publica, integracion futura"]}


def lista_corta(departamento: str, modalidad: str = "VIGILANCIA PRIVADA", armas: str | None = None,
                provincia: str | None = None, sitio: tuple[float, float] | None = None) -> pd.DataFrame:
    """Empresas autorizadas en el departamento, con puntaje, desglose y distancia al sitio."""
    from .geo import centroide, distancia_km

    emp = buscar_empresas(departamento, modalidad, armas, provincia)
    if emp.empty:
        return emp
    filas = []
    for r in emp.itertuples():
        p = puntaje_confianza(r.ruc, departamento, modalidad, armas)
        comp = {c["nombre"]: c["puntos"] for c in p["componentes"]}
        sede = centroide(departamento, r.provincias_sede.split(" | ")[0])
        filas.append({"ruc": r.ruc, "razon_social": r.razon_social, "puntaje": p["puntaje"],
                      "armas": r.armas, "vence": r.vencimiento, "provincias_sede": r.provincias_sede,
                      "sede_en_provincia": bool(r.sede_en_provincia),
                      "km_al_sitio": round(distancia_km(sede, sitio)) if sede and sitio else None,
                      "lat": sede[0] if sede else None, "lon": sede[1] if sede else None,
                      **comp, "_detalle": p})
    out = pd.DataFrame(filas)
    return out.sort_values(["puntaje", "sede_en_provincia"], ascending=False).reset_index(drop=True)
