# ðŸ›¡ï¸ Garita

> **Hacemos que contratar seguridad privada deje de ser un acto de fe para mineras y empresas en el PerÃº, verificando a cada proveedor contra SUCAMEC, OECE y SUNAT, comparando su precio con contratos pÃºblicos reales leÃ­dos con IA y mostrando el riesgo de la zona.**

**Demo:** https://garita-seguridad.streamlit.app/ Â· **Corre en local:** ver [CÃ³mo correrlo](#cÃ³mo-correrlo) Â· **Video de respaldo:** en el issue del curso

Proyecto final de Data Science con Python, Universidad del PacÃ­fico (2026-II).

---

## 1. One-liner

Hacemos la **verificaciÃ³n y comparaciÃ³n de proveedores de seguridad privada** para **mineras, puertos y plantas en el PerÃº** mediante **scraping de registros oficiales (SUCAMEC, OECE, SUNAT, DefensorÃ­a) y un LLM con salida estructurada que convierte cientos de contratos pÃºblicos en un precio por puesto-mes comparable**.

## 2. Founder

**JosÃ© Miguel DÃ­az**, <<FOUNDER>>

## 3. Problema

**QuiÃ©n lo sufre.** El jefe de seguridad patrimonial o de compras de una minera mediana, una planta o un puerto que tiene que contratar vigilancia, muchas veces en una zona de alto riesgo. Del otro lado, las empresas de seguridad formales, que pierden contratos frente a ofertas que no cubren el costo laboral.

**CÃ³mo lo resuelve hoy.**
1. Pide cotizaciones a las empresas que conoce o que le recomendaron: la contrataciÃ³n de servicios corporativos en el PerÃº depende del boca a boca y de contactos personales ([Infomercado](https://infomercado.pe/bilda-consolida-su-plataforma-b2b-de-servicios-especializados-y-busca-impulsar-la-contratacion-industrial-en-el-peru/)).
2. Verifica a mano, empresa por empresa, la autorizaciÃ³n en el [registro de SUCAMEC](https://www.sucamec.gob.pe/rgGSSP/aplicacion/resoluciones/List.xhtml). El link que piden las bases de licitaciÃ³n (`/web/index.php/empresas-de-seguridad`) hoy devuelve 404. Aparte revisa SUNAT y, si se acuerda, el buscador de proveedores del OECE.
3. Compara precios sin referencia: no sabe si una oferta barata es eficiente o si es barata porque no paga planilla.
4. Si es una minera grande, exige ademÃ¡s una homologaciÃ³n anual hecha por un tercero (ver [competencia](docs/competencia.md)).

**CuÃ¡nto le cuesta.**
- **Riesgo legal.** Si la empresa de seguridad no paga a sus trabajadores y su fianza no alcanza, la empresa usuaria responde solidariamente por los adeudos laborales ([Ley 27626, arts. 24 y 25](https://lpderecho.pe/ley-intermediacion-laboral-ley-27626/)).
- **Riesgo de seguridad.** Una empresa sin autorizaciÃ³n vigente para armas, o con personal informal, falla justo donde mÃ¡s se necesita. Pataz estÃ¡ en estado de emergencia por minerÃ­a ilegal, con las Fuerzas Armadas a cargo del orden interno ([DS 137-2026-PCM](data/manual/estados_emergencia.csv)).
- **Tiempo.** Verificar cada proveedor contra tres fuentes y comparar cotizaciones toma dÃ­as; medir cuÃ¡ntos es uno de los objetivos de las conversaciones con usuarios.
- **Informalidad del sector.** En los contratos pÃºblicos que leÃ­mos, **<<PCT_BAJO_PISO>>%** se pagan por debajo del piso legal de un puesto 24/7.

**Evidencia de usuarios.** En [`docs/research/`](docs/research/README.md) hay **3 entrevistas sintÃ©ticas**: un jefe de seguridad de una minera, el gerente de una empresa de seguridad y un analista de homologaciÃ³n. **Son personajes ficticios construidos con IA, no personas reales**, y cada dolor que expresan estÃ¡ respaldado por una fuente pÃºblica con link. Los tres coinciden por motivos distintos: hoy se contrata por boca a boca, y falta una herramienta formal que reÃºna legalidad, precio y riesgo. El comprador paga, la empresa formal gana argumentos y la homologadora es un canal. Las hipÃ³tesis H1 a H3 tienen respaldo pÃºblico; la disposiciÃ³n a pagar (H4) no tiene evidencia y es lo primero que validaremos con usuarios reales, con el plan que estÃ¡ en la misma carpeta.

## 4. SoluciÃ³n e insight

**La soluciÃ³n.** El cliente describe su necesidad (lugar, puestos, horario, perfil, armamento y equipamiento) y Garita le devuelve:

1. **El riesgo de la zona**: conflictos sociales del departamento (DefensorÃ­a), casos ubicados en la provincia y estados de emergencia vigentes, en un mapa.
2. **Una lista corta de empresas con autorizaciÃ³n vigente de SUCAMEC** para esa modalidad y departamento (y con armas si lo pide), cada una con un **puntaje de confianza de 0 a 100 que muestra de quÃ© se compone**: autorizaciÃ³n y vigencia (SUCAMEC), RUC activo y habido (SUNAT), habilitaciÃ³n para contratar con el Estado, penalidades, sanciones y contratos de vigilancia ganados (OECE), y cobertura.
3. **El precio justo**: rango de soles por puesto 24/7-mes en su departamento, el estimado de su pedido y una alerta cuando una oferta queda por debajo del **piso legal** del puesto.
4. **La lectura de cartas fianza y pÃ³lizas** con OCR y LLM, y un calendario de vencimientos (.ics).
5. **Una solicitud de propuesta** en Word y Excel lista para enviar a la lista corta.

**Cada dato dice de dÃ³nde viene**: âœ… verificado con fuente oficial (con link) Â· ðŸ”Ž extraÃ­do de un documento oficial con IA Â· ðŸ“ declarado por la empresa Â· ðŸ§ª sintÃ©tico para el demo. Nunca se presenta un dato declarado o sintÃ©tico como verificado.

**El insight.** El precio de un puesto de vigilancia sÃ­ es pÃºblico, pero estÃ¡ escondido. El Estado contrata cientos de servicios de vigilancia al aÃ±o y publica cada contrato con su monto y sus Bases. Nadie los habÃ­a leÃ­do: las Bases dicen "12 agentes, 2 turnos, 365 dÃ­as" en texto libre, casi siempre con OCR sucio o escaneadas. Garita las lee y las convierte en puestos, horas y meses, y con eso calcula por primera vez un **precio por puesto-mes comparable**: mediana nacional de **S/ <<MEDIANA_PUESTO_MES>>** sobre **<<N_CONTRATOS>> contratos** de <<N_DEPARTAMENTOS>> departamentos.

**El segundo insight.** La confianza no estÃ¡ en un solo registro. Una empresa puede estar autorizada por SUCAMEC y estar inhabilitada para contratar con el Estado o tener el RUC no habido. Cruzar las fuentes por RUC es trivial con cÃ³digo y lento a mano. Hoy solo **<<N_EMPRESAS_VIGILANCIA>> empresas** tienen autorizaciÃ³n vigente de vigilancia privada en el registro de SUCAMEC.

## 5. Why now

- **Los datos ya son abiertos y legibles por mÃ¡quina.** El OECE publica los contratos en el estÃ¡ndar OCDS con descargas mensuales y una API de proveedores; SUCAMEC mantiene en lÃ­nea su registro con fecha de vencimiento ([SUCAMEC](https://www.gob.pe/institucion/sucamec/pages/9498-empresas-de-seguridad)).
- **Leer documentos dejÃ³ de ser caro.** Hace tres aÃ±os, extraer puestos y turnos de cientos de Bases escaneadas exigÃ­a entrenar un modelo o pagarle a una persona. Hoy un LLM con salida JSON lo hace por centavos: **todo el benchmark costÃ³ US$ <<COSTO_PIPELINE>>** en llamadas a la API.
- **La seguridad en zonas mineras es mÃ¡s crÃ­tica que nunca.** El reporte N.Â° 269 de la DefensorÃ­a (agosto de 2026) registra **188 conflictos sociales**; 92 son socioambientales y **61 de ellos estÃ¡n ligados a la minerÃ­a** ([DefensorÃ­a](https://www.defensoria.gob.pe/wp-content/uploads/2026/09/Reporte-de-conflictos-sociales-n-270.pdf)). Hay **31 estados de emergencia vigentes** por decreto supremo, incluidos Pataz, la minerÃ­a ilegal de Cajamarca y Madre de Dios ([tabla curada con sus decretos](data/manual/estados_emergencia.csv)).
- **El costo laboral acaba de subir.** La remuneraciÃ³n mÃ­nima pasÃ³ de S/ 1,130 a **S/ 1,230 el 1 de octubre de 2026**, con un segundo tramo pendiente hasta S/ 1,300 ([DS 015-2026-TR](https://busquedas.elperuano.pe/dispositivo/EX/2559163-1)). Cada alza mueve el piso legal de un puesto 24/7 (hoy **S/ <<PISO_24H>>** al mes) y vuelve obsoletas las cotizaciones viejas.
- **El sector es grande y estÃ¡ fragmentado.** SUCAMEC reportaba 4,319 empresas y mÃ¡s de 125,000 agentes autorizados ([El Peruano](https://elperuano.pe/noticia/141085-sucamec-acredito-a-mas-de-125-mil-agentes-de-seguridad-en-todo-el-pais); **dato antiguo**, de alrededor de 2022). En el registro actual, Garita cuenta **<<N_EMPRESAS_SUCAMEC>> empresas** con alguna autorizaciÃ³n vigente en las modalidades que importan a un comprador.

## 6. Demo

**URL pÃºblica:** https://garita-seguridad.streamlit.app/

**El flujo del demo (2 minutos):** "vigilancia con armas, 8 puestos 24/7, campamento minero en Pataz, La Libertad" â†’ riesgo de la zona â†’ lista corta con puntaje â†’ precio y alerta de una oferta bajo el piso â†’ lectura de una carta fianza escaneada â†’ solicitud de propuesta en Word. Guion completo en [`docs/guion_demo.md`](docs/guion_demo.md).

| Pedido y riesgo de la zona | Proveedores con puntaje | Precio y piso legal |
|---|---|---|
| ![Riesgo](docs/capturas/1_riesgo.png) | ![Proveedores](docs/capturas/2_proveedores.png) | ![Precio](docs/capturas/3_precio.png) |

### Arquitectura

```mermaid
flowchart LR
    subgraph Fuentes oficiales
        S[SUCAMEC<br/>formulario JSF]
        O[OECE<br/>API OCDS + ficha de proveedores]
        N[SUNAT<br/>padrÃ³n reducido]
        D[DefensorÃ­a<br/>reporte PDF]
        G[LÃ­mites distritales<br/>sesiÃ³n 06]
    end
    subgraph Pipeline offline Â· run_pipeline.py
        S -->|03 scraping| P1[empresas autorizadas]
        O -->|03 API| P2[contratos de vigilancia<br/>+ links a Bases]
        P2 -->|10 Document AI<br/>triaje + OCR| P3[texto de TDR]
        P3 -->|08 DeepSeek JSON<br/>+ Pydantic| P4[puestos, horas, armado]
        P4 -->|Python| P5[benchmark S/ puesto-mes]
        O -->|03 API| P6[penalidades, inhabilitaciÃ³n]
        N -->|03| P7[RUC activo y habido]
        D -->|03 + 10| P8[conflictos por regiÃ³n y provincia]
        G -->|06 GeoPandas| P9[provincias]
    end
    P1 & P5 & P6 & P7 & P8 & P9 --> DP[(data/processed<br/>versionado = modo demo)]
    DP --> APP[App Streamlit Â· 05]
    DP --> MCP[MCP garita Â· 04]
    MCP --> SK[Skill evaluar-proveedor Â· 16]
    APP -->|en vivo, opcional| LLM[DeepSeek: pedido en texto libre<br/>y lectura de documentos]
```

### Modelos y APIs, y por quÃ©

| QuÃ© | Para quÃ© | Por quÃ© este |
|---|---|---|
| **DeepSeek `deepseek-chat`** con el SDK de OpenAI y `response_format` JSON | Leer las Bases (puestos, horas, armado, perfil), entender el pedido y leer documentos | El mÃ¡s barato con JSON fiable en espaÃ±ol: el benchmark completo costÃ³ US$ <<COSTO_PIPELINE>>. Mismo patrÃ³n que el HW3. |
| **Pydantic** | Validar cada respuesta del LLM; un reintento con el error | Un nÃºmero que no valida no entra al benchmark: un hueco es mejor que un dato inventado |
| **PaddleOCR / RapidOCR (modelos PP-OCR en ONNX)** | PÃ¡ginas escaneadas de las Bases y documentos subidos | PaddleOCR es el de la sesiÃ³n 10; en Streamlit Cloud no cabe, asÃ­ que corren los mismos modelos PP-OCR en ONNX |
| **PyMuPDF** | Capa de texto y rasterizado de pÃ¡ginas | RÃ¡pido y sin dependencias de sistema |
| **API OCDS y buscador de proveedores del OECE** | Contratos, montos, plazos, Bases, inhabilitaciones y penalidades | Fuente oficial, abierta y por RUC |
| **GeoPandas + Folium** | Provincias disueltas desde distritos y mapa de riesgo | Herramientas de la sesiÃ³n 06 |
| **Streamlit Community Cloud** | Despliegue gratuito | URL pÃºblica con secretos para la clave |

## 7. Modelo de negocio

**QuiÃ©n paga.** La empresa que contrata seguridad: mineras medianas, plantas y puertos. No el proveedor de seguridad, para que la recomendaciÃ³n sea neutral.

| Producto | Precio | QuÃ© incluye |
|---|---|---|
| **Garita Empresa** | **S/ 1,500 al mes** por empresa compradora | VerificaciÃ³n, benchmark de precios, riesgo por zona, lectura de documentos, alertas de vencimiento y solicitudes de propuesta ilimitadas |
| ComisiÃ³n (etapa 2) | 3 % a 5 % del contrato cuando Garita intermedia la contrataciÃ³n | Convocatoria y gestiÃ³n del contrato |
| Perfil premium (etapa 2) | SuscripciÃ³n para empresas de seguridad | Perfil y documentos al dÃ­a; **no altera el puntaje** |

Ejemplo de la comisiÃ³n: 8 puestos 24/7 a la mediana de S/ <<MEDIANA_PUESTO_MES>> por 12 meses son S/ <<CONTRATO_EJEMPLO>>; el 3 % es S/ <<COMISION_EJEMPLO>>.

**Costo por usuario** (precios de DeepSeek verificados el 20/09/2026, con su tarifa por franja horaria en [`garita/costos.py`](garita/costos.py)):

| Concepto | Costo | Fuente |
|---|---|---|
| NormalizaciÃ³n de los contratos (pipeline) | **US$ <<COSTO_PIPELINE>>** por corrida (<<N_LLAMADAS>> llamadas, ~<<TOKENS_POR_PROCESO>> tokens por proceso), una vez al mes y compartido entre todos los clientes | [`logs/costos.csv`](logs/costos.csv) |
| Una consulta en la app (pedido o documento) | ~<<TOKENS_POR_CONSULTA>> tokens, **US$ <<COSTO_POR_CONSULTA>>** | `logs/costos.csv`; referencia del HW3 del autor: 32 llamadas por US$ 0.013, entre US$ 0.0003 y 0.0012 cada una |
| Uso tÃ­pico de un cliente al mes (**estimado**) | 4 contrataciones Ã— ~6 llamadas = 24 llamadas â‰ˆ **US$ <<COSTO_CLIENTE_MES>>** | Supuesto a validar con usuarios |
| Servidor del demo | US$ 0 (Streamlit Community Cloud) | |
| Servidor en producciÃ³n (**estimado**) | US$ 20 a 40 al mes compartidos | Una mÃ¡quina virtual pequeÃ±a |

El costo variable en tokens es menos del 0.1 % del precio. El costo real es vender y mantener los datos al dÃ­a, no el cÃ³mputo. Tope de gasto: `GARITA_TOPE_USD` (por defecto US$ 3); al alcanzarlo, la app sigue en modo demo.

## 8. Herramientas del curso y dÃ³nde estÃ¡n

**Las dos que justifican la rÃºbrica:**

1. **Scraping y APIs (sesiÃ³n 03).** Sin ella no hay producto: replica el formulario JSF de SUCAMEC (ViewState, botÃ³n Buscar y paginador de PrimeFaces, por departamento porque el buscador corta en 2,000), consume la API OCDS y la ficha de proveedores del OECE, el padrÃ³n de SUNAT y el Ã­ndice de reportes de la DefensorÃ­a. Automatiza la verificaciÃ³n que hoy se hace a mano. â†’ [`garita/sucamec.py`](garita/sucamec.py), [`garita/oece.py`](garita/oece.py), [`garita/sunat.py`](garita/sunat.py), [`garita/defensoria.py`](garita/defensoria.py), [`garita/red.py`](garita/red.py)
2. **LLMs con salidas estructuradas (sesiÃ³n 08).** Es el insight: convierte Bases en texto libre y OCR sucio en puestos, horas, armado, plazo y perfil, en JSON validado con Pydantic, para que Python calcule un precio por puesto-mes que hoy no existe. â†’ [`garita/esquemas.py`](garita/esquemas.py), [`garita/llm.py`](garita/llm.py), [`garita/extraccion.py`](garita/extraccion.py), [`garita/costos.py`](garita/costos.py), [`garita/benchmark.py`](garita/benchmark.py)

**TambiÃ©n dentro del producto:**

| Herramienta | Para quÃ© | DÃ³nde |
|---|---|---|
| Document AI (10) | Triaje texto/imagen, OCR solo en pÃ¡ginas escaneadas, TDR de las Bases, cuadros de la DefensorÃ­a, documentos subidos | [`garita/documentos.py`](garita/documentos.py), [`garita/defensoria.py`](garita/defensoria.py) |
| GeoPandas y Folium (06) | Provincias desde distritos, centroides, distancia sedeâ€“sitio, mapa de riesgo | [`garita/geo.py`](garita/geo.py) |
| Dashboards (05) | La app de 6 pestaÃ±as | [`app.py`](app.py) |
| MCP (04) | "Garita para Claude": 8 herramientas de consulta, plugin instalable | [`mcp_server/server.py`](mcp_server/server.py), [`.claude-plugin/`](.claude-plugin/) |
| Skills de Claude Code (16) | Skill del producto `evaluar-proveedor-seguridad` y 4 de desarrollo | [`skills/`](skills/), [`.claude/skills/`](.claude/skills/) |
| Despliegue y evaluaciÃ³n (12) | Streamlit Cloud con modo demo; LLM contra lÃ­nea base de reglas | [`eval/evaluar_extraccion.py`](eval/evaluar_extraccion.py) |

El detalle por subcategorÃ­a (quÃ© parte descarga, cuÃ¡l lee los labels, cuÃ¡l limpia, cuÃ¡l guarda) estÃ¡ en [`docs/mapa_herramientas.md`](docs/mapa_herramientas.md); cada secciÃ³n estÃ¡ marcada en el cÃ³digo con `# ===== HERRAMIENTA NN` y `# --- NN.k`.

**EvaluaciÃ³n (sesiÃ³n 12).** Sobre los <<N_EVAL>> procesos con TDR legible:

<<TABLA_EVAL>>

### Garita para Claude (MCP + skill)

Un analista de compras puede usar los mismos datos desde Claude: el MCP pone los datos y la skill pone el mÃ©todo.

```text
/plugin marketplace add josemigueldiaz1/Garita-StartupProject
/plugin install garita@garita
```

Luego: *"EvalÃºa estas tres propuestas de seguridad para un campamento en Pataz"*. En este repo, `.mcp.json` ya registra el servidor para Claude Code.

## 9. QuÃ© hizo el agente

Este proyecto se construyÃ³ con **Claude Code (Claude Opus 5.5)** en una sesiÃ³n de trabajo guiada por el founder.

| Parte | QuiÃ©n |
|---|---|
| Idea, problema, decisiÃ³n de enfocar en confianza y precio, requisitos del servicio, reglas de datos | JosÃ© |
| BÃºsqueda y prueba de las fuentes: hallazgo del registro JSF de SUCAMEC (el link de las bases da 404), del tope de 2,000 resultados, de la ficha JSON del OECE, del padrÃ³n de SUNAT y de los cuadros de la DefensorÃ­a | Claude Code |
| Todo el cÃ³digo de `garita/`, `app.py`, `run_pipeline.py` y `eval/` | Claude Code |
| Servidor MCP, plugin, skills y pruebas (`mcp_server/`, `skills/`, `.claude/skills/`, `tests/`) | Un subagente de Claude Code en paralelo |
| InvestigaciÃ³n de competencia, guÃ­a de conversaciones, plantilla, guion, borrador del README y tabla de estados de emergencia con sus decretos | Otro subagente de Claude Code en paralelo |
| Conversaciones con usuarios, revisiÃ³n, clave de la API, despliegue y presentaciÃ³n | JosÃ© |

**CÃ³digo reutilizado de las tareas del autor** ([repo de tareas](https://github.com/josemigueldiaz1/repo-JoseMiguelDiaz)):
- `HW3_Diaz/tarea2_radar/src/adquisicion.py` â†’ base de [`garita/oece.py`](garita/oece.py) (API OCDS, descarga mensual con cachÃ©, una fila por ocid).
- `HW3_Diaz/tarea1_rag_normativo/src/costos.py` â†’ [`garita/costos.py`](garita/costos.py) (registro por llamada y tarifa por franja de DeepSeek; se agregÃ³ el tope de gasto).
- `HW3_Diaz/tarea1_rag_normativo/src/motor.py` â†’ el patrÃ³n de [`garita/llm.py`](garita/llm.py) (cliente de OpenAI con `base_url` de DeepSeek y `response_format` JSON; se agregÃ³ Pydantic).
- Curso: el servidor MCP sigue el patrÃ³n de `sessions/04-mcp-claude-code`, el triaje de Document AI la regla de `sessions/10-document-ai-voz/lab/src/triaje.py` y los lÃ­mites distritales vienen de `sessions/06-geoespacial`.

---

## CÃ³mo correrlo

Necesitas Python 3.12 (uv lo instala si no lo tienes) y git.

**Windows (PowerShell)**
```powershell
pip install uv            # o: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
git clone https://github.com/josemigueldiaz1/Garita-StartupProject.git
cd Garita-StartupProject
uv sync
uv run streamlit run app.py
```

**macOS y Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/josemigueldiaz1/Garita-StartupProject.git
cd Garita-StartupProject
uv sync
uv run streamlit run app.py
```

La app abre en `http://localhost:8501` y funciona **sin clave** (modo demo con los datos de `data/processed`). Para las funciones con IA en vivo, crea `.env` en la raÃ­z del repo con `DEEPSEEK_API_KEY=` y tu clave (en Windows: `notepad .env`; hay un ejemplo en `.env.example`).

Sin uv: `python -m venv .venv`, actÃ­valo (`.venv\Scripts\activate` en Windows, `source .venv/bin/activate` en macOS/Linux), `pip install -r requirements.txt` y `streamlit run app.py`.

**Regenerar los datos**
```bash
uv run python run_pipeline.py                                  # fuentes, sin LLM
uv run python run_pipeline.py --pasos documentos,extraer,benchmark   # gasta tokens, con tope
uv sync --group ocr                                            # PaddleOCR en local (opcional)
uv run python eval/evaluar_extraccion.py                       # LLM contra lÃ­nea base
uv run pytest                                                  # pruebas
```

**Despliegue en Streamlit Community Cloud:** `app.py`, Python 3.12, y en *Settings â†’ Secrets* `DEEPSEEK_API_KEY = "..."` y `GARITA_TOPE_USD = "1.00"`. `requirements.txt` y `packages.txt` ya estÃ¡n en el repo.

## Datos y privacidad

Solo datos de **empresas**: nunca nombres, DNI, fotos ni medidas de vigilantes. La estatura o la edad son requisitos que pide el cliente, no una base de personas. Del padrÃ³n de SUNAT solo se guardan RUC de personas jurÃ­dicas (20). Los documentos de ejemplo son **sintÃ©ticos** y lo dicen en su encabezado. El diccionario de datos y los niveles estÃ¡n en [`docs/datos.md`](docs/datos.md).

## Licencia

MIT. Ver [LICENSE](LICENSE).
