"""
Garita · la app. Contratar seguridad privada confiable en el Peru, con datos oficiales.

    uv run streamlit run app.py

La app solo LEE data/processed (modo demo): nunca descarga fuentes ni llama al LLM para
construir los datos. El LLM se usa en vivo solo para dos cosas pequenas y opcionales:
entender el pedido escrito en lenguaje natural y leer un documento subido. Sin clave o
sin presupuesto, ambas caen a reglas y el flujo sigue completo.
"""

from __future__ import annotations

import io
import json
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from garita import datos
from garita.benchmark import costo_laboral_minimo, evaluar_oferta
from garita.config import load_config
from garita.pedido import (ARMAS, EQUIPAMIENTO, TIPOS_SITIO, Pedido, avisos_armamento, calendario_ics,
                           documento_por_reglas, interpretar_por_reglas, solicitud_docx,
                           solicitud_xlsx)

# ===== HERRAMIENTA 05 · Dashboards (Streamlit) =====
# --- 05.1 Pagina: configuracion, estilos y estado de la sesion
st.set_page_config(page_title="Garita · seguridad privada verificada", page_icon="🛡️",
                   layout="wide")
cfg = load_config()
AZUL, AZUL_CLARO, CRITICO, TINTA, MUTED = "#2a78d6", "#cde2fb", "#d03b3b", "#0b0b0b", "#898781"
NIVELES = {"verificado": "✅ verificado", "extraido": "🔎 extraído de documento oficial",
           "declarado": "📝 declarado", "sintetico": "🧪 sintético (demo)", "sin_dato": "— sin dato"}
EJEMPLO = ("Necesito vigilancia con armas, 8 puestos 24/7 para un campamento minero en Pataz, "
           "La Libertad, por 12 meses. Con radios y control de accesos.")

st.markdown("""<style>
.block-container {padding-top: 1.6rem;}
.garita-nota {font-size: 0.85rem; color: #52514e;}
.garita-chip {display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.78rem;
              background: rgba(42,120,214,0.10); margin-right:4px;}
</style>""", unsafe_allow_html=True)

# Cada campo del pedido es un widget con clave fija en st.session_state. Antes los widgets
# se creaban con value=<valor anterior>: cada clic cambiaba ese valor, Streamlit los
# trataba como widgets nuevos y "retrocedian" mientras llegaban los clics siguientes.
CLAVES = {"departamento": "p_dep", "provincia": "p_prov", "tipo_sitio": "p_sitio",
          "modalidad": "p_modalidad", "con_armas": "p_armas", "tipo_arma": "p_tipo_arma",
          "n_puestos": "p_npuestos", "horas_por_dia": "p_horas", "dias_por_semana": "p_dias",
          "plazo_meses": "p_plazo", "supervisor": "p_supervisor", "estatura_min_m": "p_estatura",
          "edad_max": "p_edad", "experiencia_min_meses": "p_exp", "idiomas": "p_idiomas",
          "licencia_conducir": "p_licencia", "curso_sucamec": "p_curso", "equipamiento": "p_equip",
          "notas": "p_notas"}
OPCIONES = {"p_horas": [24, 12, 8], "p_dias": [7, 6, 5]}
IDIOMAS = ["Castellano", "Quechua", "Aimara", "Inglés"]
DEPARTAMENTOS = cfg.sucamec["departamentos"]
_base = Pedido()
for _campo, _clave in CLAVES.items():
    st.session_state.setdefault(_clave, getattr(_base, _campo))
st.session_state.setdefault("p_texto", EJEMPLO)
st.session_state.setdefault("region_mapa", _base.departamento)
st.session_state.setdefault("vencimientos", [])
P = Pedido(**{campo: st.session_state[clave] for campo, clave in CLAVES.items()})


def _validar(clave: str, opciones: list) -> None:
    """Si el valor guardado ya no esta entre las opciones (cambio el departamento), usa la primera."""
    if st.session_state.get(clave) not in opciones:
        st.session_state[clave] = opciones[0]


@st.cache_resource
def _llm():
    from garita.llm import ClienteLLM
    return ClienteLLM(cfg)


def llm_disponible() -> tuple[bool, str]:
    try:
        return _llm().disponible()
    except Exception as e:  # noqa: BLE001
        return False, str(e)


@st.cache_data(show_spinner=False)
def _lista(dep: str, prov: str, modalidad: str, armas: str | None) -> pd.DataFrame:
    from garita.confianza import lista_corta
    from garita.geo import centroide

    return lista_corta(dep, modalidad, armas, prov, centroide(dep, prov))


@st.cache_data(show_spinner=False)
def _provincias(dep: str) -> list[str]:
    c = datos.tabla("centroides_distritos")
    return sorted(c.loc[c["departamento"] == dep, "provincia"].unique()) if not c.empty else []


@st.cache_data(show_spinner=False)
def _ranking() -> pd.DataFrame:
    return datos.ranking_regiones()


def nivel(n: str) -> str:
    return NIVELES.get(n, n)


# --- 05.11 Callbacks: corren antes del rerun, por eso pueden escribir en los widgets
def _interpretar() -> None:
    """Boton "Interpretar pedido": LLM si hay clave, reglas siempre como respaldo."""
    texto = st.session_state.p_texto
    campos, origen = {}, "reglas"
    ok, _ = llm_disponible()
    if ok:
        try:
            from garita.extraccion import interpretar_pedido

            obj, uso = interpretar_pedido(texto)
            campos = {k: v for k, v in obj.model_dump().items() if v not in (None, [], "")}
            origen = f"IA · {uso['tokens_entrada'] + uso['tokens_salida']} tokens · US${uso['costo_usd']:.5f}"
        except Exception as e:  # noqa: BLE001 - cae a reglas
            st.session_state.p_aviso = f"La IA no respondió ({str(e)[:80]}). Se usaron reglas."
    for k, v in interpretar_por_reglas(texto).items():
        campos.setdefault(k, v)
    for campo, valor in campos.items():
        clave = CLAVES.get(campo)
        if not clave or campo in ("equipamiento", "notas", "modalidad"):
            continue
        if campo in ("departamento", "provincia"):
            valor = datos.normalizar(valor)
            if campo == "departamento" and valor not in DEPARTAMENTOS:
                continue
        elif campo == "tipo_sitio" and valor not in TIPOS_SITIO:
            continue
        elif clave in OPCIONES:
            valor = min(OPCIONES[clave], key=lambda o: abs(o - int(valor)))
        elif campo == "con_armas":
            valor = bool(valor)
        elif campo in ("n_puestos", "plazo_meses"):
            valor = int(min(max(int(valor), 1), 500 if campo == "n_puestos" else 60))
        st.session_state[clave] = valor
    equipo = list(st.session_state.p_equip)
    for e in campos.get("equipamiento", []) or []:
        for opcion in EQUIPAMIENTO:
            palabras = [w for w in datos.normalizar(e).split() if len(w) > 4]
            if any(w in datos.normalizar(opcion) for w in palabras) and opcion not in equipo:
                equipo.append(opcion)
    if "ACCESO" in datos.normalizar(texto) and "Control de accesos" not in equipo:
        equipo.append("Control de accesos")
    st.session_state.p_equip = equipo
    st.session_state.region_mapa = st.session_state.p_dep
    st.session_state.p_msg = f"Pedido interpretado ({origen}). Revisa y ajusta el detalle abajo."


def _sincronizar_region() -> None:
    st.session_state.region_mapa = st.session_state.p_dep


def _usar_region() -> None:
    """Boton del mapa: lleva la region explorada al pedido."""
    region = st.session_state.region_mapa
    st.session_state.p_dep = region
    provs = _provincias(region)
    if provs and st.session_state.p_prov not in provs:
        st.session_state.p_prov = provs[0]


meta = datos.metadatos()
ok_llm, motivo_llm = llm_disponible()

# --- 05.2 Barra lateral: que es Garita, modo de la app y fechas de corte
with st.sidebar:
    st.title("🛡️ Garita")
    st.caption(cfg.proyecto["one_liner"])
    if ok_llm:
        st.success("IA en vivo disponible (DeepSeek) con tope de gasto.", icon="✅")
    else:
        st.info(f"Modo demo: {motivo_llm} Todo el flujo funciona con datos ya procesados.", icon="ℹ️")
    st.markdown("**Fuentes y fecha de corte**")
    for clave, nombre in [("sucamec", "SUCAMEC"), ("oece", "OECE contratos"),
                          ("proveedores_oece", "OECE proveedores"), ("sunat", "SUNAT padrón"),
                          ("defensoria", "Defensoría"), ("delitos", "Delitos INEI"),
                          ("benchmark", "Benchmark")]:
        m = meta.get(clave, {})
        extra = f" · {m['reporte']} ({m.get('mes', '')})" if clave == "defensoria" and m.get("reporte") else ""
        st.markdown(f"<span class='garita-nota'>{nombre}: {m.get('fecha_corte', 'pendiente')}{extra}</span>",
                    unsafe_allow_html=True)
    st.markdown("<span class='garita-nota'>Cada dato lleva su nivel: ✅ verificado con fuente oficial · "
                "🔎 extraído de un documento oficial · 📝 declarado · 🧪 sintético.</span>",
                unsafe_allow_html=True)
    st.markdown("[Código en GitHub](https://github.com/josemigueldiaz1/Garita-StartupProject)")

st.title("Contrata seguridad privada sin adivinar")
st.markdown("Verificamos a las empresas contra **SUCAMEC, OECE y SUNAT**, comparamos el precio con "
            "**contratos públicos reales** y te mostramos el **riesgo de la zona**. Una empresa sin "
            "autorización vigente, o una oferta que no alcanza para pagar planilla, es un riesgo para "
            "tu operación y para tu gente.")

t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Pedido", "2 · Mapa de riesgo", "3 · Proveedores",
                                  "4 · Precio", "5 · Documentos", "6 · Solicitud de propuesta"])

# --- 05.3 Pestana 1: el pedido, en texto libre (LLM o reglas) y en detalle
with t1:
    st.subheader("¿Qué necesitas proteger?")
    st.text_area("Descríbelo como se lo dirías a un proveedor", key="p_texto", height=80)
    c1, c2 = st.columns([1, 3])
    c1.button("Interpretar pedido", type="primary", on_click=_interpretar)
    if st.session_state.get("p_aviso"):
        c2.warning(st.session_state.pop("p_aviso"))
    if st.session_state.get("p_msg"):
        c2.success(st.session_state.pop("p_msg"))

    with st.expander("📍 Lugar", expanded=True):
        a, b, c = st.columns(3)
        _validar("p_dep", DEPARTAMENTOS)
        a.selectbox("Departamento", DEPARTAMENTOS, key="p_dep", on_change=_sincronizar_region)
        provs = _provincias(st.session_state.p_dep) or [st.session_state.p_prov]
        _validar("p_prov", provs)
        b.selectbox("Provincia", provs, key="p_prov")
        _validar("p_sitio", TIPOS_SITIO)
        c.selectbox("Tipo de sitio", TIPOS_SITIO, key="p_sitio")
    with st.expander("👮 Personal y horario", expanded=True):
        a, b, c, d = st.columns(4)
        a.number_input("Puestos", min_value=1, max_value=500, step=1, key="p_npuestos")
        _validar("p_horas", OPCIONES["p_horas"])
        b.selectbox("Horas por día", OPCIONES["p_horas"], key="p_horas")
        _validar("p_dias", OPCIONES["p_dias"])
        c.selectbox("Días por semana", OPCIONES["p_dias"], key="p_dias")
        d.number_input("Plazo (meses)", min_value=1, max_value=60, step=1, key="p_plazo")
        st.markdown("**Perfil exigido** <span class='garita-nota'>(requisito tuyo que la empresa declara "
                    "cumplir; Garita no guarda datos de vigilantes)</span>", unsafe_allow_html=True)
        a, b, c, d = st.columns(4)
        a.number_input("Estatura mínima (m)", min_value=1.50, max_value=1.90, step=0.01, format="%.2f",
                       key="p_estatura")
        b.number_input("Edad máxima", min_value=25, max_value=70, step=1, key="p_edad")
        c.number_input("Experiencia mínima (meses)", min_value=0, max_value=240, step=6, key="p_exp")
        st.session_state.p_idiomas = [i for i in st.session_state.p_idiomas if i in IDIOMAS]
        d.multiselect("Idiomas", IDIOMAS, key="p_idiomas")
        a, b, c = st.columns(3)
        a.toggle("Supervisor de turno", key="p_supervisor")
        b.toggle("Licencia de conducir", key="p_licencia")
        c.toggle("Curso SUCAMEC vigente", key="p_curso")
    with st.expander("🔫 Armamento y 📡 equipamiento", expanded=True):
        a, b = st.columns(2)
        a.toggle("Con armas de fuego", key="p_armas")
        if st.session_state.p_armas:
            _validar("p_tipo_arma", ARMAS)
            b.selectbox("Tipo de arma", ARMAS, key="p_tipo_arma")
            b.caption("SUCAMEC verifica que la empresa esté autorizada **con armas**; el tipo de arma lo "
                      "declara la empresa. Opciones según el Reglamento de la Ley 30299 (DS 010-2017-IN, "
                      "art. 19); prohibidas las automáticas y de características militares (art. 16).")
            _p_armas = Pedido(**{campo: st.session_state[clave] for campo, clave in CLAVES.items()})
            for _nivel, _msg in avisos_armamento(_p_armas):
                (st.error if _nivel == "error" else st.warning)(_msg, icon="⚖️")
        st.session_state.p_equip = [e for e in st.session_state.p_equip if e in EQUIPAMIENTO]
        st.multiselect("Equipamiento", list(EQUIPAMIENTO), key="p_equip")
        verificables = [e for e in st.session_state.p_equip if EQUIPAMIENTO[e]]
        if verificables:
            st.caption("✅ Se verifica contra SUCAMEC (autorización de tecnología de seguridad): " +
                       ", ".join(verificables) + ". El resto lo declara la empresa.")
        st.text_input("Notas para los proveedores", key="p_notas")
    P = Pedido(**{campo: st.session_state[clave] for campo, clave in CLAVES.items()})
    st.info(f"**Tu pedido:** {P.n_puestos} puestos de {P.horas_por_dia} h, {P.dias_por_semana} días, "
            f"{'con' if P.con_armas else 'sin'} armas, {P.tipo_sitio} en {P.provincia.title()} "
            f"({P.departamento.title()}), {P.plazo_meses} meses. Equivale a "
            f"{P.puestos_equivalentes_24h:.1f} puestos 24/7.", icon="🧾")

# --- 05.4 Pestana 2: mapa de riesgo y oferta por region (cualquier region del Peru)
ICONO_MOTIVO = [("MINERIA", "⛏️ Minería ilegal"), ("NARCO", "🌿 Narcotráfico"), ("CRIMIN", "🎯 Crimen organizado"),
                ("VIOLENCIA", "🎯 Violencia y criminalidad"), ("EXTORSION", "🎯 Extorsión")]


def _etiqueta_motivo(motivo: str) -> str:
    m = datos.normalizar(motivo)
    return next((etq for clave, etq in ICONO_MOTIVO if clave in m), "🚨 Otro motivo")


with t2:
    from garita.geo import CAPAS, mapa_region
    from streamlit_folium import st_folium

    st.subheader("🗺️ Mapa de riesgo y proveedores por región")
    a, b = st.columns([1, 2])
    _validar("region_mapa", DEPARTAMENTOS)
    region = a.selectbox("Región a explorar", DEPARTAMENTOS, key="region_mapa", format_func=str.title)
    capa = b.radio("Colorear el mapa por", list(CAPAS), horizontal=True, key="capa_mapa")
    if region != P.departamento:
        a.button(f"Usar {region.title()} en mi pedido", on_click=_usar_region)

    rk = _ranking().set_index("departamento")
    f = rk.loc[region]
    prov_pedido = P.provincia if region == P.departamento else None
    r = datos.riesgo_zona(region, prov_pedido)
    em_region = datos.estados_emergencia(region)
    anio = int(f["anio"]) if pd.notna(f.get("anio")) else 2024

    # --- 05.12 Tarjetas: cuatro senales de la region, cada una con su fuente
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔫 Delitos por 10 mil hab.", f"{f['tasa_10mil']:,.0f}",
              help=f"Denuncias por comisión de delitos registradas por la PNP (SIDPOL), {anio}. Fuente: INEI.")
    c1.caption(f"{int(f['denuncias']):,} denuncias en {anio} · puesto {int(f['ranking_tasa'])} de 25 · "
               f"{nivel('verificado')}")
    c2.metric("⚠️ Conflictos sociales", int(f["conflictos"]),
              help="Cuadro 3 del reporte mensual de la Defensoría del Pueblo.")
    c2.caption(f"{int(f.get('activos', 0))} activos · Defensoría {r.get('reporte', '')} · {nivel('verificado')}")
    c3.metric("🚨 Estados de emergencia", len(em_region))
    c3.caption("Decretos supremos vigentes en la región · " + nivel("verificado"))
    c4.metric("🛡️ Empresas autorizadas", int(f["empresas_vigilancia"]),
              help="Empresas con autorización vigente de SUCAMEC para vigilancia privada con sede en la región.")
    c4.caption(f"{int(f['empresas_con_armas'])} con armas · SUCAMEC · {nivel('verificado')}")

    tasa_p75 = rk["tasa_10mil"].quantile(0.75)
    alto = len(em_region) > 0 or f["tasa_10mil"] >= tasa_p75 or f["conflictos"] >= 10
    medio = f["tasa_10mil"] >= rk["tasa_10mil"].median() or f["conflictos"] >= 4
    lugar = f"{prov_pedido.title()}, {region.title()}" if prov_pedido else region.title()
    if alto:
        st.error(f"**Riesgo alto en {lugar}.** Prioriza vigilancia **con armas**, sede cercana, supervisión "
                 "24 h y un plan de contingencia y de relacionamiento con la comunidad. En zonas así, el "
                 "precio más bajo suele ser el más caro.", icon="🚨")
    elif medio:
        st.warning(f"**Riesgo medio en {lugar}.** Exige supervisión, protocolo de relevo y tiempos de "
                   "respuesta por escrito.", icon="⚠️")
    else:
        st.success(f"**Riesgo bajo en {lugar} según las fuentes oficiales.** Igual verifica autorización "
                   "y planilla.", icon="✅")
    for e in em_region.itertuples():
        st.markdown(f"- {_etiqueta_motivo(e.motivo)} · **{(e.provincia or e.departamento).title()}**"
                    f"{' (' + e.distrito.replace('|', ', ').title() + ')' if e.distrito else ''} · {e.norma} · "
                    f"{'hasta ' + pd.Timestamp(e.fecha_fin).strftime('%d/%m/%Y') if pd.notna(e.fecha_fin) else 'vigencia por confirmar'}"
                    f" · [decreto]({e.url})")

    # ===== HERRAMIENTA 06 · GeoPandas y Folium =====
    # --- 06.4 Mapa en la app: Peru por region, la region elegida, emergencias, conflictos y empresas
    m, nombre_capa = mapa_region(region, prov_pedido, capa, datos.empresas_por_provincia(region))
    st_folium(m, height=540, use_container_width=True, returned_objects=[], key="mapa_region")
    st.caption(f"**Color de cada región:** {nombre_capa}; más oscuro = más alto. "
               "🟠 burbuja: empresas con sede autorizada en la provincia (más grande = más empresas) · "
               "🔴 estado de emergencia (◆ minería ilegal, ⊕ crimen organizado, 🍃 narcotráfico) · "
               "🔥 casos del reporte de la Defensoría · ★ tu sitio. Pasa el cursor por el mapa para ver los números.")

    st.markdown(f"**Provincias de {region.title()}**")
    pr = datos.provincias_region(region).sort_values(["empresas", "n_casos"], ascending=False)
    st.dataframe(pr.rename(columns={"provincia": "Provincia", "empresas": "🛡️ Empresas con sede",
                                    "con_armas": "🔫 De ellas con armas", "n_casos": "⚠️ Casos Defensoría",
                                    "emergencia": "🚨 Estado de emergencia"}),
                 hide_index=True, width="stretch", height=min(38 * (len(pr) + 1), 360))

    # --- 05.13 Grafico: la region elegida frente a las otras 24
    with st.expander("📊 Comparar con otras regiones"):
        col, titulo = CAPAS[capa]
        comp = rk.reset_index()[["departamento", col]].rename(columns={col: "valor"})
        comp["region"] = comp["departamento"].str.title()
        barras = alt.Chart(comp).mark_bar(cornerRadiusEnd=4, height=12).encode(
            x=alt.X("valor:Q", title=titulo),
            y=alt.Y("region:N", sort="-x", title=None, axis=alt.Axis(labelLimit=160)),
            color=alt.condition(alt.datum.departamento == region, alt.value(AZUL), alt.value(AZUL_CLARO)),
            tooltip=[alt.Tooltip("region:N", title="Región"), alt.Tooltip("valor:Q", title=titulo, format=",.1f")])
        st.altair_chart(barras.properties(height=25 * len(comp)), width="stretch")

    fuentes = [("INEI · denuncias por departamento", datos.metadatos().get("delitos", {}).get("url", "")),
               (f"Defensoría del Pueblo · reporte {r.get('reporte', '')}", r.get("fuente", "")),
               ("SUCAMEC · empresas autorizadas", cfg.sucamec["url"])]
    st.caption("Fuentes: " + " · ".join(f"[{n}]({u})" for n, u in fuentes if u) +
               " · estados de emergencia: decretos supremos en El Peruano (tabla curada en el repo).")

# --- 05.5 Pestana 3: lista corta con puntaje de confianza y su desglose
with t3:
    lista = _lista(P.departamento, P.provincia, P.modalidad, P.armas)
    st.subheader(f"Empresas autorizadas para {P.modalidad.lower()}"
                 f"{' con armas' if P.con_armas else ''} en {P.departamento.title()}")
    if lista.empty:
        st.warning("Ninguna empresa tiene autorización vigente para esa modalidad en el departamento.")
    else:
        a, b, c = st.columns(3)
        minimo = a.slider("Puntaje mínimo", 0, 100, 50, 5)
        solo_prov = b.toggle(f"Solo con sede en {P.provincia.title()}", False)
        tec = [EQUIPAMIENTO[e] for e in P.equipamiento if EQUIPAMIENTO[e]]
        exigir_tec = c.toggle("Exigir tecnología autorizada (CCTV, accesos, GPS)", False, disabled=not tec,
                              help="Deja solo empresas que además tienen autorización vigente de SUCAMEC "
                                   "para prestar tecnología de seguridad (en cualquier sede del país).")
        f = lista[lista["puntaje"] >= minimo]
        if solo_prov:
            f = f[f["sede_en_provincia"]]
        if exigir_tec and tec:
            res = datos.tabla("sucamec_resoluciones")
            con_tec = set(res[res["modalidad"].str.startswith("TECNOLOGIA") & res["vigente"]]["ruc"])
            f = f[f["ruc"].isin(con_tec)]
        st.caption(f"{len(lista)} empresas autorizadas · {len(f)} cumplen tus filtros · "
                   f"{nivel('verificado')} contra el registro de SUCAMEC del {meta.get('sucamec', {}).get('fecha_corte', '')}")
        vista = f[["razon_social", "ruc", "puntaje", "armas", "vence", "provincias_sede", "km_al_sitio"]].rename(
            columns={"razon_social": "Empresa", "ruc": "RUC", "puntaje": "Puntaje", "armas": "Armas",
                     "vence": "Autorización vence", "provincias_sede": "Sedes en el departamento",
                     "km_al_sitio": "Km al sitio (línea recta)"})
        st.dataframe(vista, hide_index=True, width="stretch",
                     column_config={"Puntaje": st.column_config.ProgressColumn(min_value=0, max_value=100,
                                                                               format="%d"),
                                    "Autorización vence": st.column_config.DateColumn(format="DD/MM/YYYY")})
        if not f.empty:
            elegido = st.selectbox("Ver el detalle de una empresa", f["razon_social"] + " · " + f["ruc"])
            fila = f[f["ruc"] == elegido.split(" · ")[-1]].iloc[0]
            det = fila["_detalle"]
            a, b = st.columns([2, 3])
            a.metric("Puntaje de confianza", f"{det['puntaje']} / 100")
            comps = pd.DataFrame(det["componentes"])
            # --- 05.6 Grafico: desglose del puntaje (barra de puntos sobre su maximo)
            base = alt.Chart(comps).encode(y=alt.Y("nombre:N", sort=None, title=None,
                                                   axis=alt.Axis(labelLimit=260)))
            pista = base.mark_bar(color="#e1e0d9", cornerRadiusEnd=4, height=14).encode(
                x=alt.X("maximo:Q", title="Puntos", scale=alt.Scale(domain=[0, 30])))
            barra = base.mark_bar(color=AZUL, cornerRadiusEnd=4, height=14).encode(
                x="puntos:Q", tooltip=[alt.Tooltip("nombre:N", title="Componente"),
                                       alt.Tooltip("puntos:Q", title="Puntos"),
                                       alt.Tooltip("maximo:Q", title="Máximo"),
                                       alt.Tooltip("detalle:N", title="Detalle")])
            b.altair_chart((pista + barra).properties(height=230), width="stretch")
            for c_ in det["componentes"]:
                st.markdown(f"- **{c_['nombre']}** · {c_['puntos']:g}/{c_['maximo']} · {nivel(c_['nivel'])} · "
                            f"{c_['detalle']} [fuente]({c_['fuente']})")
            for p_ in det["pendientes"]:
                st.markdown(f"<span class='garita-nota'>⏳ {p_}</span>", unsafe_allow_html=True)
            auts = datos.modalidades_de(fila["ruc"])
            if not auts.empty:
                with st.expander(f"Autorizaciones SUCAMEC vigentes ({len(auts)})"):
                    st.dataframe(auts[["modalidad", "armas", "departamento", "provincia", "resolucion",
                                       "fecha_vencimiento", "sede"]], hide_index=True, width="stretch")
            hist = datos.contratos_vigilancia(ruc_proveedor=fila["ruc"], solo_validos=False)
            if not hist.empty:
                with st.expander(f"Contratos públicos de vigilancia ({len(hist)})"):
                    st.dataframe(hist[["entidad", "departamento", "monto_contrato", "fecha_firma", "duracion_dias"]],
                                 hide_index=True, width="stretch")

# --- 05.7 Pestana 4: benchmark de precio, piso legal y evaluacion de una oferta
with t4:
    bm = datos.benchmark(P.departamento)
    piso = costo_laboral_minimo(P.horas_por_dia, P.dias_por_semana, cfg)
    piso24 = costo_laboral_minimo(24, 7, cfg)
    st.subheader("¿Cuánto debería costar?")
    if not bm:
        st.warning("El benchmark todavía no está construido (falta correr el paso `benchmark`).")
    else:
        if bm.get("motivo"):
            st.caption(bm["motivo"])
        a, b, c, d = st.columns(4)
        a.metric("Mediana por puesto 24/7-mes", f"S/ {bm['mediana']:,.0f}",
                 help="Sin IGV. Los contratos públicos incluyen IGV: su monto se divide entre 1.18 (salvo en "
                      "Loreto, Ucayali y Madre de Dios, exonerados por la Ley 27037) para compararlo con "
                      "cotizaciones 'más IGV' y con el piso de planilla.")
        a.caption(f"sin IGV · {bm['alcance']} · n = {bm['n']} contratos · {nivel('extraido')}")
        b.metric("Rango típico (p25 – p75)", f"{bm['p25'] / 1000:,.1f} – {bm['p75'] / 1000:,.1f} mil",
                 help=f"S/ {bm['p25']:,.0f} a S/ {bm['p75']:,.0f} sin IGV: la mitad de los contratos cae en este rango.")
        b.caption(f"con IGV: S/ {bm['mediana'] * 1.18:,.0f} de mediana")
        c.metric("Piso legal de un puesto 24/7", f"S/ {piso24.piso_puesto_mes:,.0f}",
                 help="Solo la planilla: RMV, recargo nocturno, EsSalud, SCTR, Vida Ley, gratificaciones, "
                      "CTS y vacaciones de los agentes necesarios. Sin utilidad ni gastos generales.")
        c.caption(f"{piso24.agentes_necesarios} agentes con RMV S/ {piso24.supuestos['rmv']:,.0f} "
                  f"({cfg.costo_laboral['rmv_norma']})")
        d.metric("Contratos públicos bajo el piso", f"{bm.get('pct_bajo_piso', 0):.0f}%",
                 help="Cada contrato se compara con el piso de la RMV vigente cuando se firmó.")
        d.caption("Señal de informalidad, no prueba")
        equiv = P.puestos_equivalentes_24h
        est_bajo, est_med, est_alto = (bm["p25"] * equiv, bm["mediana"] * equiv, bm["p75"] * equiv)
        st.info(f"**Estimado para tu pedido** ({equiv:.1f} puestos 24/7 equivalentes): "
                f"S/ {est_med:,.0f} al mes sin IGV (rango S/ {est_bajo:,.0f} – {est_alto:,.0f}); "
                f"S/ {est_med * P.plazo_meses:,.0f} por {P.plazo_meses} meses, S/ "
                f"{est_med * P.plazo_meses * 1.18:,.0f} con IGV. "
                f"El piso legal de planilla de tu configuración es S/ {piso.piso_puesto_mes * P.n_puestos:,.0f} al mes.",
                icon="🧮")
        st.session_state.setdefault("oferta", 7000)
        oferta = st.number_input("Evalúa una oferta: precio por puesto y mes, sin IGV (S/)", min_value=0,
                                 max_value=100000, step=100, key="oferta")
        ev = evaluar_oferta(oferta, P.horas_por_dia, bm, cfg)
        mensajes = {"bajo_piso": (st.error, "🚨 Debajo del piso legal: no alcanza para pagar planilla completa. "
                                             "Pide la estructura de costos antes de seguir."),
                    "bajo_mercado": (st.warning, "⚠️ Debajo del 75% del mercado: revisa qué incluye."),
                    "sobre_mercado": (st.warning, "⚠️ Sobre el percentil 75: negocia o pide sustento."),
                    "en_rango": (st.success, "✅ Dentro del rango de contratos comparables.")}
        fn, txt = mensajes[ev["estado"]]
        fn(f"{txt} (piso legal S/ {ev['piso_legal']:,.0f})")

        # --- 05.8 Grafico: contratos comparables, rango tipico, piso legal y la oferta
        cont = datos.contratos_vigilancia(P.departamento if bm["alcance"] == "departamental" else None)
        if not cont.empty:
            cont = cont.assign(armado_txt=cont["armado"].map({"si": "con armas", "no": "sin armas"}).fillna("no indica"))
            puntos = alt.Chart(cont).mark_circle(size=90, color=AZUL, opacity=0.75, stroke="white",
                                                 strokeWidth=1).encode(
                x=alt.X("precio_puesto_mes:Q", title="Soles por puesto 24/7 y mes, sin IGV"),
                y=alt.Y("jitter:Q", axis=None, title=None),
                tooltip=[alt.Tooltip("entidad:N", title="Entidad"),
                         alt.Tooltip("departamento:N", title="Departamento"),
                         alt.Tooltip("precio_puesto_mes:Q", title="S/ por puesto-mes", format=",.0f"),
                         alt.Tooltip("puestos_equivalentes_24h:Q", title="Puestos 24/7 equiv.", format=".1f"),
                         alt.Tooltip("meses:Q", title="Meses", format=".1f"),
                         alt.Tooltip("armado_txt:N", title="Armado"),
                         alt.Tooltip("monto_contrato:Q", title="Monto S/", format=",.0f")]
            ).transform_calculate(jitter="random()")
            banda = alt.Chart(pd.DataFrame([bm])).mark_rect(color=AZUL_CLARO, opacity=0.6).encode(
                x="p25:Q", x2="p75:Q")
            # Cada etiqueta en su propia fila (y) para que no se pisen cuando la oferta
            # esta cerca del piso.
            reglas = pd.DataFrame([{"x": piso24.piso_puesto_mes, "etiqueta": "Piso legal", "color": CRITICO,
                                    "y": 8},
                                   {"x": oferta * 24 / P.horas_por_dia, "etiqueta": "Oferta evaluada",
                                    "color": TINTA, "y": 24}])
            lineas = alt.Chart(reglas).mark_rule(strokeWidth=2).encode(
                x="x:Q", color=alt.Color("color:N", scale=None))
            textos = alt.Chart(reglas).mark_text(align="left", dx=4, fontSize=11).encode(
                x="x:Q", y=alt.Y("y:Q", scale=None, axis=None), text="etiqueta:N", color=alt.value("#52514e"))
            st.altair_chart((banda + puntos + lineas + textos).properties(height=220), width="stretch")
            st.caption("Cada punto es un contrato público de vigilancia. La banda celeste es el rango típico "
                       "(p25–p75). Puestos y horas leídos de las Bases con IA, monto y plazo del contrato firmado.")
            with st.expander("Ver los contratos y la evidencia de cada extracción"):
                cont = cont.assign(url_registro="https://contratacionesabiertas.oece.gob.pe/api/v1/record/" + cont["ocid"])
                st.dataframe(cont[["entidad", "departamento", "monto_contrato", "meses", "n_puestos",
                                   "puestos_equivalentes_24h", "n_agentes", "precio_puesto_mes", "confianza",
                                   "evidencia", "url_registro", "url_bases"]],
                             hide_index=True, width="stretch",
                             column_config={"url_registro": st.column_config.LinkColumn("Registro OECE",
                                                                                         display_text="ver registro"),
                                            "url_bases": st.column_config.LinkColumn("Bases (SEACE)",
                                                                                     display_text="descargar PDF"),
                                            "precio_puesto_mes": st.column_config.NumberColumn(
                                                "S/ por puesto-mes (sin IGV)", format="S/ %,.0f"),
                                            "monto_contrato": st.column_config.NumberColumn(format="S/ %,.0f")})
                st.caption("El registro OECE es la API oficial de datos abiertos (siempre disponible). El PDF se "
                           "descarga del servidor de SEACE, que a veces no responde (devolvía error 404 el "
                           "18/11/2026 de madrugada). Por eso Garita guarda el texto que leyó de cada Bases:")

                # --- 05.14 Evidencia: el texto que Document AI leyo de las Bases, guardado en el repo
                textos = datos.tabla("tdr_textos")
                if not textos.empty:
                    opciones = cont["ocid"].tolist()
                    nombres = dict(zip(cont["ocid"], cont["entidad"].str.slice(0, 70) + " · S/ " +
                                       cont["precio_puesto_mes"].round(0).astype(int).astype(str)))
                    elegido = st.selectbox("Ver el texto leído de las Bases de un contrato", opciones,
                                           format_func=lambda o: nombres.get(o, o), key="ver_tdr")
                    t = textos[textos["ocid"] == elegido]
                    fila = cont[cont["ocid"] == elegido].iloc[0]
                    st.markdown(f"**Lo que extrajo el LLM:** {int(fila['n_puestos'] or 0)} puestos · "
                                f"{fila['puestos_equivalentes_24h']:.1f} puestos 24/7 equivalentes · "
                                f"{'' if pd.isna(fila.get('n_agentes')) else str(int(fila['n_agentes'])) + ' agentes · '}"
                                f"cita: _{fila['evidencia']}_")
                    if not t.empty:
                        st.caption(f"Páginas leídas: {t.iloc[0]['paginas_tdr']} de {int(t.iloc[0]['paginas_totales'])} · "
                                   f"{int(t.iloc[0]['paginas_ocr'])} con OCR · {nivel('extraido')}")
                        st.text(t.iloc[0]["texto_tdr"][:6000])
        with st.expander("¿Cómo se calcula el piso legal?"):
            st.json(piso24.a_dict())

# --- 05.9 Pestana 5: documentos del proveedor (Document AI + LLM) y vencimientos
with t5:
    st.subheader("Lee cartas fianza, pólizas y autorizaciones")
    st.caption("Sube el PDF que te entregó el proveedor. Si es un escaneo, pasa por OCR; luego se extraen "
               "montos y fechas. Nivel del dato: 📝 declarado (documento del proveedor, no verificado con el emisor).")
    a, b, c = st.columns(3)
    subido = a.file_uploader("PDF del proveedor", type=["pdf"])
    ejemplo = None
    if b.button("Usar carta fianza de ejemplo 🧪"):
        ejemplo = "carta_fianza_sintetica.pdf"
    if c.button("Usar la versión escaneada 🧪"):
        ejemplo = "carta_fianza_sintetica_escaneada.pdf"
    contenido = subido.getvalue() if subido else (
        (cfg.demo_dir / ejemplo).read_bytes() if ejemplo else None)
    if contenido:
        # ===== HERRAMIENTA 10 · Document AI =====
        # --- 10.8 En la app: triaje y OCR del documento subido
        from garita.documentos import leer_documento

        with st.spinner("Leyendo el documento (triaje y OCR si hace falta)..."):
            doc = leer_documento(contenido, cfg)
        motores = ", ".join(sorted({p.motor for p in doc.paginas}))
        st.caption(f"{doc.paginas_totales} página(s) · {doc.paginas_ocr} con OCR · motor: {motores}")
        campos, origen = None, "reglas (modo demo)"
        if ok_llm and doc.texto.strip():
            try:
                from garita.extraccion import extraer_documento

                obj, uso = extraer_documento(doc.texto)
                campos = obj.model_dump()
                origen = f"IA · US${uso['costo_usd']:.5f}"
            except Exception as e:  # noqa: BLE001
                st.warning(f"La IA no respondió ({str(e)[:80]}); se usan reglas.")
        if campos is None:
            campos = documento_por_reglas(doc.texto)
        sintetico = "SINTETICO" in datos.normalizar(doc.texto)
        st.markdown(f"**Datos extraídos** ({origen}) · {nivel('sintetico' if sintetico else 'declarado')}")
        st.dataframe(pd.DataFrame([{"Campo": k, "Valor": f"{v:,.2f}" if isinstance(v, float) else str(v)}
                                   for k, v in campos.items() if v not in (None, "")]),
                     hide_index=True, width="stretch")
        if campos.get("fecha_vencimiento"):
            vence = date.fromisoformat(str(campos["fecha_vencimiento"])[:10])
            dias = (vence - date.today()).days
            if dias < 0:
                st.error(f"🚨 Vencido hace {-dias} días.")
            elif dias <= 30:
                st.warning(f"⚠️ Vence en {dias} días ({vence:%d/%m/%Y}).")
            else:
                st.success(f"✅ Vigente: vence en {dias} días ({vence:%d/%m/%Y}).")
            evento = (f"Vence {campos.get('tipo_documento', 'documento')} {campos.get('numero') or ''}".strip(),
                      vence, f"Monto: {campos.get('monto')} {campos.get('moneda') or ''}")
            if evento not in st.session_state.vencimientos:
                st.session_state.vencimientos.append(evento)
        with st.expander("Texto leído"):
            st.text(doc.texto[:4000])

    st.markdown("#### Calendario de vencimientos")
    lista = _lista(P.departamento, P.provincia, P.modalidad, P.armas)
    eventos = list(st.session_state.vencimientos)
    for r_ in lista.head(5).itertuples():
        if pd.notna(r_.vence):
            eventos.append((f"Vence autorización SUCAMEC de {r_.razon_social}", pd.Timestamp(r_.vence).date(),
                            f"RUC {r_.ruc} · verificado en SUCAMEC"))
    if eventos:
        tabla_v = pd.DataFrame(eventos, columns=["Evento", "Fecha", "Detalle"]).sort_values("Fecha")
        tabla_v["Días restantes"] = [(f - date.today()).days for f in tabla_v["Fecha"]]
        tabla_v["Estado"] = ["🚨 Vencido" if d < 0 else "⚠️ Vence pronto" if d <= 30 else "✅ Vigente"
                             for d in tabla_v["Días restantes"]]
        tabla_v = tabla_v[["Estado", "Evento", "Fecha", "Días restantes", "Detalle"]]
        st.dataframe(tabla_v, hide_index=True, width="stretch")
        a, b = st.columns(2)
        excel = io.BytesIO()
        tabla_v.assign(Estado=tabla_v["Estado"].str[2:]).to_excel(excel, index=False, sheet_name="Vencimientos")
        a.download_button("📊 Descargar en Excel", excel.getvalue(), "garita_vencimientos.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        b.download_button("📅 Agregar a mi calendario (.ics)", calendario_ics(eventos),
                          "garita_vencimientos.ics", "text/calendar",
                          help="Archivo de calendario: ábrelo con Outlook (doble clic) o impórtalo en Google "
                               "Calendar (Configuración → Importar). Crea cada vencimiento con un aviso 30 días antes.")

# --- 05.10 Pestana 6: solicitud de propuesta exportable
with t6:
    st.subheader("Solicitud de propuesta lista para enviar")
    lista = _lista(P.departamento, P.provincia, P.modalidad, P.armas)
    if lista.empty:
        st.warning("No hay empresas autorizadas para invitar con este pedido.")
    else:
        opciones = (lista["razon_social"] + " · " + lista["ruc"]).tolist()
        elegidas = st.multiselect("Empresas a invitar", opciones, opciones[:5])
        inv = lista[(lista["razon_social"] + " · " + lista["ruc"]).isin(elegidas)]
        bm = datos.benchmark(P.departamento)
        piso24 = costo_laboral_minimo(24, 7, cfg).piso_puesto_mes
        a, b, c = st.columns(3)
        a.download_button("📄 Descargar en Word", solicitud_docx(P, inv, bm, piso24),
                          "solicitud_propuesta_garita.docx",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                          type="primary")
        b.download_button("📊 Descargar en Excel (con comparativo)", solicitud_xlsx(P, inv, bm, piso24),
                          "solicitud_propuesta_garita.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if c.button("💾 Guardar pedido"):
            try:
                ruta = cfg.pedidos_dir / f"pedido_{date.today():%Y%m%d}_{P.provincia.lower().replace(' ', '_')}.json"
                ruta.write_text(json.dumps(P.a_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
                c.success(f"Guardado en {ruta.relative_to(cfg.root)}")
            except OSError:
                c.info("En la nube el pedido vive en tu sesión; descárgalo en Word o Excel.")
        st.markdown("**Incluye:** requerimiento completo, documentos exigidos (autorización SUCAMEC, SUNAT, "
                    "carta fianza, SCTR y Vida Ley, estructura de costos), referencia de precio, piso legal, "
                    "empresas invitadas con su puntaje y criterios de evaluación.")
