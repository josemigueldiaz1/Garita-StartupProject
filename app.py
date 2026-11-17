"""
Garita · la app. Contratar seguridad privada confiable en el Peru, con datos oficiales.

    uv run streamlit run app.py

La app solo LEE data/processed (modo demo): nunca descarga fuentes ni llama al LLM para
construir los datos. El LLM se usa en vivo solo para dos cosas pequenas y opcionales:
entender el pedido escrito en lenguaje natural y leer un documento subido. Sin clave o
sin presupuesto, ambas caen a reglas y el flujo sigue completo.
"""

from __future__ import annotations

import json
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from garita import datos
from garita.benchmark import costo_laboral_minimo, evaluar_oferta
from garita.config import load_config
from garita.pedido import (ARMAS, EQUIPAMIENTO, TIPOS_SITIO, Pedido, calendario_ics,
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

if "pedido" not in st.session_state:
    st.session_state.pedido = Pedido()
if "vencimientos" not in st.session_state:
    st.session_state.vencimientos = []
P: Pedido = st.session_state.pedido


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


def nivel(n: str) -> str:
    return NIVELES.get(n, n)


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
                          ("defensoria", "Defensoría"), ("benchmark", "Benchmark")]:
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

t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Pedido", "2 · Riesgo de la zona", "3 · Proveedores",
                                  "4 · Precio", "5 · Documentos", "6 · Solicitud de propuesta"])

# --- 05.3 Pestana 1: el pedido, en texto libre (LLM o reglas) y en detalle
with t1:
    st.subheader("¿Qué necesitas proteger?")
    texto = st.text_area("Descríbelo como se lo dirías a un proveedor", value=EJEMPLO, height=80)
    c1, c2 = st.columns([1, 3])
    if c1.button("Interpretar pedido", type="primary"):
        campos, origen = {}, "reglas"
        if ok_llm:
            try:
                from garita.extraccion import interpretar_pedido

                with st.spinner("Leyendo tu pedido con IA..."):
                    obj, uso = interpretar_pedido(texto)
                campos = {k: v for k, v in obj.model_dump().items() if v not in (None, [], "")}
                if "con_armas" in campos:
                    campos["con_armas"] = bool(campos["con_armas"])
                if "n_puestos" not in campos:
                    campos.update({k: v for k, v in interpretar_por_reglas(texto).items() if k == "n_puestos"})
                origen = f"IA · {uso['tokens_entrada'] + uso['tokens_salida']} tokens · US${uso['costo_usd']:.5f}"
            except Exception as e:  # noqa: BLE001 - cae a reglas
                st.warning(f"La IA no respondió ({str(e)[:80]}). Se usan reglas.")
        if not campos:
            campos = interpretar_por_reglas(texto)
        for k, v in campos.items():
            if hasattr(P, k) and k not in ("equipamiento", "notas"):
                setattr(P, k, datos.normalizar(v) if k in ("departamento", "provincia") else v)
        for e in campos.get("equipamiento", []) or []:
            for opcion in EQUIPAMIENTO:
                if any(w in datos.normalizar(opcion) for w in datos.normalizar(e).split() if len(w) > 4):
                    if opcion not in P.equipamiento:
                        P.equipamiento.append(opcion)
        if "ACCESO" in datos.normalizar(texto) and "Control de accesos" not in P.equipamiento:
            P.equipamiento.append("Control de accesos")
        c2.success(f"Pedido interpretado ({origen}). Revisa y ajusta el detalle abajo.")

    deps = cfg.sucamec["departamentos"]
    with st.expander("📍 Lugar", expanded=True):
        a, b, c = st.columns(3)
        P.departamento = a.selectbox("Departamento", deps, index=deps.index(P.departamento)
                                     if P.departamento in deps else 0)
        provs = _provincias(P.departamento) or [P.provincia]
        P.provincia = b.selectbox("Provincia", provs, index=provs.index(P.provincia)
                                  if P.provincia in provs else 0)
        P.tipo_sitio = c.selectbox("Tipo de sitio", TIPOS_SITIO, index=TIPOS_SITIO.index(P.tipo_sitio)
                                   if P.tipo_sitio in TIPOS_SITIO else 0)
    with st.expander("👮 Personal y horario", expanded=True):
        a, b, c, d = st.columns(4)
        P.n_puestos = a.number_input("Puestos", 1, 500, int(P.n_puestos))
        P.horas_por_dia = b.selectbox("Horas por día", [24, 12, 8], index=[24, 12, 8].index(P.horas_por_dia)
                                      if P.horas_por_dia in (24, 12, 8) else 0)
        P.dias_por_semana = c.selectbox("Días por semana", [7, 6, 5], index=[7, 6, 5].index(P.dias_por_semana)
                                        if P.dias_por_semana in (7, 6, 5) else 0)
        P.plazo_meses = d.number_input("Plazo (meses)", 1, 60, int(P.plazo_meses))
        st.markdown("**Perfil exigido** <span class='garita-nota'>(requisito tuyo que la empresa declara "
                    "cumplir; Garita no guarda datos de vigilantes)</span>", unsafe_allow_html=True)
        a, b, c, d = st.columns(4)
        P.estatura_min_m = a.number_input("Estatura mínima (m)", 1.50, 1.90, float(P.estatura_min_m), 0.01)
        P.edad_max = b.number_input("Edad máxima", 25, 70, int(P.edad_max))
        P.experiencia_min_meses = c.number_input("Experiencia mínima (meses)", 0, 240, int(P.experiencia_min_meses))
        P.idiomas = d.multiselect("Idiomas", ["Castellano", "Quechua", "Aimara", "Inglés"], P.idiomas)
        a, b, c = st.columns(3)
        P.supervisor = a.toggle("Supervisor de turno", P.supervisor)
        P.licencia_conducir = b.toggle("Licencia de conducir", P.licencia_conducir)
        P.curso_sucamec = c.toggle("Curso SUCAMEC vigente", P.curso_sucamec)
    with st.expander("🔫 Armamento y 📡 equipamiento", expanded=True):
        a, b = st.columns(2)
        P.con_armas = a.toggle("Con armas de fuego", P.con_armas)
        if P.con_armas:
            P.tipo_arma = b.selectbox("Tipo de arma", ARMAS, index=ARMAS.index(P.tipo_arma)
                                      if P.tipo_arma in ARMAS else 0)
            b.caption("SUCAMEC verifica que la empresa esté autorizada **con armas**; el tipo de arma lo "
                      "declara la empresa.")
        P.equipamiento = st.multiselect("Equipamiento", list(EQUIPAMIENTO), P.equipamiento)
        verificables = [e for e in P.equipamiento if EQUIPAMIENTO[e]]
        if verificables:
            st.caption("✅ Se verifica contra SUCAMEC: " + ", ".join(verificables) +
                       ". El resto lo declara la empresa.")
        P.notas = st.text_input("Notas para los proveedores", P.notas)
    st.info(f"**Tu pedido:** {P.n_puestos} puestos de {P.horas_por_dia} h, {P.dias_por_semana} días, "
            f"{'con' if P.con_armas else 'sin'} armas, {P.tipo_sitio} en {P.provincia.title()} "
            f"({P.departamento.title()}), {P.plazo_meses} meses. Equivale a "
            f"{P.puestos_equivalentes_24h:.1f} puestos 24/7.", icon="🧾")

# --- 05.4 Pestana 2: riesgo de la zona (Defensoria + estados de emergencia + mapa)
with t2:
    r = datos.riesgo_zona(P.departamento, P.provincia)
    st.subheader(f"Riesgo en {P.provincia.title()}, {P.departamento.title()}")
    a, b, c = st.columns(3)
    a.metric("Conflictos sociales en el departamento", r.get("conflictos_departamento", "—"),
             help="Cuadro 3 del reporte mensual de la Defensoría del Pueblo.")
    a.caption(f"Puesto {r.get('ranking_departamento', '—')} de 25 · {r.get('activos_departamento', 0)} activos · "
              f"{nivel('verificado')}")
    b.metric("Casos ubicados en la provincia", r.get("casos_provincia", 0),
             help="Casos que el reporte ubica en la provincia (alertas, mediación, acuerdos). Es un mínimo.")
    b.caption(f"{r.get('reporte', '')} · {r.get('mes', '')}")
    em = r.get("estados_emergencia", [])
    c.metric("Estados de emergencia vigentes", len(em))
    c.caption("Decretos supremos vigentes en la zona · " + nivel("verificado"))
    alto = bool(em) or r.get("conflictos_departamento", 0) >= 10 or r.get("casos_provincia", 0) >= 2
    medio = r.get("conflictos_departamento", 0) >= 4 or r.get("casos_provincia", 0) >= 1
    if alto:
        st.error("**Riesgo alto.** Prioriza empresas con vigilancia **con armas**, sede cercana, supervisión "
                 "24 h y un plan de contingencia y de relacionamiento con la comunidad. En zonas así, el "
                 "precio más bajo suele ser el más caro.", icon="🚨")
    elif medio:
        st.warning("**Riesgo medio.** Exige supervisión, protocolo de relevo y tiempos de respuesta por "
                   "escrito.", icon="⚠️")
    else:
        st.success("**Riesgo bajo según las fuentes oficiales.** Igual verifica autorización y planilla.",
                   icon="✅")
    for e in em:
        st.markdown(f"- **{e.get('provincia') or e.get('departamento')}**: {e.get('motivo', '')} · "
                    f"{e.get('norma', '')} · hasta {e.get('fecha_fin', '')} · [fuente]({e.get('url', '')})")

    # ===== HERRAMIENTA 06 · GeoPandas y Folium =====
    # --- 06.4 Mapa en la app: provincias por casos, sitio del cliente y sedes de la lista corta
    from garita.geo import mapa_riesgo
    from streamlit_folium import st_folium

    lista = _lista(P.departamento, P.provincia, P.modalidad, P.armas)
    sedes = lista.head(15).rename(columns={"provincias_sede": "provincia"}) if not lista.empty else None
    m = mapa_riesgo(P.departamento, P.provincia, sedes)
    if m is not None:
        st_folium(m, height=470, use_container_width=True, returned_objects=[])
        st.caption("Color: casos ubicados por la Defensoría en cada provincia (gris = ninguno). ★ tu sitio · "
                   "● sedes autorizadas de las 15 mejores empresas. No es un índice de criminalidad.")
    for caso in r.get("casos", [])[:5]:
        st.markdown(f"<span class='garita-nota'>• {caso['caso']} ({caso.get('tipo') or 'tipo no indicado'}, "
                    f"p. {caso['pagina']})</span>", unsafe_allow_html=True)
    if r.get("fuente"):
        st.caption(f"Fuente: [Defensoría del Pueblo, {r.get('reporte')}]({r['fuente']})")

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
        exigir_tec = c.toggle("Exigir tecnología autorizada (CCTV, accesos, GPS)", False, disabled=not tec)
        f = lista[lista["puntaje"] >= minimo]
        if solo_prov:
            f = f[f["sede_en_provincia"]]
        if exigir_tec and tec:
            res = datos.tabla("sucamec_resoluciones")
            con_tec = set(res[res["modalidad"].isin(tec) & res["vigente"]]["ruc"])
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
            base = alt.Chart(comps).encode(y=alt.Y("nombre:N", sort=None, title=None))
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
        a.metric("Mediana por puesto 24/7-mes", f"S/ {bm['mediana']:,.0f}")
        a.caption(f"{bm['alcance']} · n = {bm['n']} contratos · {nivel('extraido')}")
        b.metric("Rango típico (p25 – p75)", f"S/ {bm['p25']:,.0f} – {bm['p75']:,.0f}")
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
                f"S/ {est_med:,.0f} al mes (rango S/ {est_bajo:,.0f} – {est_alto:,.0f}); "
                f"S/ {est_med * P.plazo_meses:,.0f} por {P.plazo_meses} meses. "
                f"El piso legal de tu configuración es S/ {piso.piso_puesto_mes * P.n_puestos:,.0f} al mes.",
                icon="🧮")
        oferta = st.number_input("Evalúa una oferta: precio por puesto y mes (S/)", 0, 100000,
                                 int(bm["p25"] * 0.75 if bm.get("p25") else 7000), 100)
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
                x=alt.X("precio_puesto_mes:Q", title="Soles por puesto 24/7 y mes"),
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
            reglas = pd.DataFrame([{"x": piso24.piso_puesto_mes, "etiqueta": "Piso legal", "color": CRITICO},
                                   {"x": oferta * 24 / P.horas_por_dia, "etiqueta": "Oferta evaluada",
                                    "color": TINTA}])
            lineas = alt.Chart(reglas).mark_rule(strokeWidth=2).encode(
                x="x:Q", color=alt.Color("color:N", scale=None))
            textos = alt.Chart(reglas).mark_text(align="left", dx=4, dy=-6, fontSize=11).encode(
                x="x:Q", y=alt.value(8), text="etiqueta:N", color=alt.value("#52514e"))
            st.altair_chart((banda + puntos + lineas + textos).properties(height=220), width="stretch")
            st.caption("Cada punto es un contrato público de vigilancia. La banda celeste es el rango típico "
                       "(p25–p75). Puestos y horas leídos de las Bases con IA, monto y plazo del contrato firmado.")
            with st.expander("Ver los contratos y la evidencia de cada extracción"):
                st.dataframe(cont[["entidad", "departamento", "monto_contrato", "meses", "n_puestos",
                                   "puestos_equivalentes_24h", "armado", "precio_puesto_mes", "confianza",
                                   "evidencia", "url_bases"]],
                             hide_index=True, width="stretch",
                             column_config={"url_bases": st.column_config.LinkColumn("Bases"),
                                            "precio_puesto_mes": st.column_config.NumberColumn(format="S/ %,.0f"),
                                            "monto_contrato": st.column_config.NumberColumn(format="S/ %,.0f")})
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
        st.dataframe(pd.DataFrame([{"Campo": k, "Valor": v} for k, v in campos.items() if v not in (None, "")]),
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
        st.dataframe(pd.DataFrame(eventos, columns=["Evento", "Fecha", "Detalle"]).sort_values("Fecha"),
                     hide_index=True, width="stretch")
        st.download_button("Descargar al calendario (.ics, aviso 30 días antes)", calendario_ics(eventos),
                           "garita_vencimientos.ics", "text/calendar")

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
