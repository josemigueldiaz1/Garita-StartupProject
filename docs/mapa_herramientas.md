# Mapa de herramientas del curso en el código

Cada trozo de código dedicado a una herramienta del curso está delimitado en el script con:

```python
# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.1 Descarga: ...
```

Para encontrar una sección: busca su número en el repositorio (por ejemplo `03.2` o `08.4`).

**Las dos que cuentan para la rúbrica son 03 (Scraping y APIs) y 08 (LLMs con salidas estructuradas).** El resto también está dentro del producto y suma.

## 03 · Scraping y APIs

| Subcategoría | Archivo | Función |
|---|---|---|
| 03.0 Cliente HTTP: pausa entre peticiones, reintentos y descarga atómica | `garita/red.py` | `Cliente`, `decodificar` |
| 03.1 Descarga: abre el formulario de SUCAMEC y guarda la sesión y el ViewState | `garita/sucamec.py` | `FormularioSucamec.abrir` |
| 03.2 Lectura: replica el botón Buscar y el paginador de PrimeFaces; detecta las celdas de cada fila | `garita/sucamec.py` | `FormularioSucamec.buscar`, `FormularioSucamec.pagina`, `leer_filas`, `descargar_modalidad` |
| 03.3 Limpieza: normaliza RUC, fechas, ubigeo, modalidad y con/sin armas | `garita/sucamec.py` | `limpiar`, `resumir_empresas` |
| 03.4 Salida: `sucamec_resoluciones.parquet` y `empresas.parquet` | `garita/sucamec.py` | `ejecutar` |
| 03.5 Descarga: catálogo de meses y ZIP mensual de la API OCDS del OECE | `garita/oece.py` | `descargar_meses` |
| 03.6 Lectura: une siete tablas del ZIP en una fila por proceso de vigilancia | `garita/oece.py` | `procesos_de_vigilancia` |
| 03.7 Limpieza: RUC del ganador, consorcios, departamento canónico y montos | `garita/oece.py` | `limpiar_contratos`, `experiencia_publica` |
| 03.8 Descarga: ficha pública del proveedor (inhabilitación, penalidades, sanciones) | `garita/oece.py` | `ficha_proveedor`, `fichas` |
| 03.9 Salida: `contratos_vigilancia.parquet` y `experiencia_publica.parquet` | `garita/oece.py` | `ejecutar` |
| 03.10 Descarga: padrón reducido del RUC de SUNAT | `garita/sunat.py` | `descargar_padron` |
| 03.11 Lectura y limpieza: filtra los RUC de interés línea por línea | `garita/sunat.py` | `filtrar_padron` |
| 03.12 Salida: `sunat_ruc.parquet` | `garita/sunat.py` | `ejecutar` |
| 03.13 Descarga: el reporte de conflictos más reciente desde el índice de la Defensoría | `garita/defensoria.py` | `ultimo_reporte` |
| 03.14 Descarga: Excel de denuncias y tasa de delitos por departamento del INEI (SIDPOL) | `garita/delitos.py` | `descargar` |
| 03.15 Lectura: detecta la fila de años y toma el último año con datos | `garita/delitos.py` | `_leer` |
| 03.16 Limpieza y salida: departamentos canónicos, Lima sumada, ranking | `garita/delitos.py` | `ejecutar` |

## 08 · LLMs con salidas estructuradas

| Subcategoría | Archivo | Función |
|---|---|---|
| 08.1 Esquemas: lo que el modelo devuelve al leer unas Bases | `garita/esquemas.py` | `Puesto`, `Perfil`, `ExtraccionTDR` |
| 08.2 Esquemas: lo que devuelve al leer un documento del proveedor | `garita/esquemas.py` | `ExtraccionDocumento` |
| 08.3 Esquemas: el pedido del cliente en lenguaje natural | `garita/esquemas.py` | `PedidoTexto` |
| 08.4 Cliente: DeepSeek con el SDK de OpenAI, `response_format` JSON y validación Pydantic con un reintento | `garita/llm.py` | `ClienteLLM.estructurado`, `ClienteLLM.disponible` |
| 08.5 Cálculo: la aritmética del benchmark la hace Python, no el modelo | `garita/benchmark.py` | `costo_laboral_minimo`, `precio_puesto_mes`, `construir`, `evaluar_oferta` |
| 08.6 Costos: tokens, latencia y dólares de cada llamada, con tope de gasto | `garita/costos.py` | `RegistroCostos`, `TopeAlcanzado` |
| 08.7 Prompts: instrucciones para leer Bases, documentos y pedidos | `garita/extraccion.py` | `SISTEMA_TDR`, `USUARIO_TDR`, `SISTEMA_DOC`, `SISTEMA_PEDIDO` |
| 08.8 Lote: extrae todos los procesos con caché por ocid | `garita/extraccion.py` | `extraer_proceso`, `ejecutar` |
| 08.9 En la app: leer un documento subido y entender un pedido | `garita/extraccion.py` | `extraer_documento`, `interpretar_pedido` |
| 08.10 Respaldo sin LLM: el pedido con reglas en modo demo | `garita/pedido.py` | `interpretar_por_reglas` |
| 08.11 Respaldo sin LLM: fechas y montos de un documento con regex | `garita/pedido.py` | `documento_por_reglas` |

## 10 · Document AI

| Subcategoría | Archivo | Función |
|---|---|---|
| 10.1 Motor: PaddleOCR si está instalado, RapidOCR (modelos PP-OCR en ONNX) si no | `garita/documentos.py` | `motor_ocr`, `ocr_imagen` |
| 10.2 Triaje: clasifica cada página en texto o imagen (regla de oro de la sesión 10) | `garita/documentos.py` | `triaje` |
| 10.3 Localización: puntúa páginas y elige el bloque de términos de referencia | `garita/documentos.py` | `leer_tdr`, `leer_documento` |
| 10.4 Salida: descarga las Bases y guarda el texto de sus TDR | `garita/documentos.py` | `seleccionar_procesos`, `ejecutar` |
| 10.5 Lectura: bloques de caso del reporte de la Defensoría con tipo y ubicación | `garita/defensoria.py` | `leer_casos` |
| 10.6 Lectura: cuadros oficiales por región y por actividad | `garita/defensoria.py` | `leer_cuadros` |
| 10.7 Salida: conflictos por caso, provincia y departamento | `garita/defensoria.py` | `ejecutar` |
| 10.8 En la app: triaje y OCR del documento que sube el usuario | `app.py` | pestaña 5 |

## 06 · GeoPandas y Folium

| Subcategoría | Archivo | Función |
|---|---|---|
| 06.1 Capa: disuelve 1,834 distritos en 197 provincias y calcula centroides en UTM | `garita/geo.py` | `construir_capas` |
| 06.2 Unión: conflictos por provincia sobre la capa | `garita/geo.py` | `unir_conflictos` |
| 06.3 Mapa nacional: regiones coloreadas por delitos, conflictos o empresas; región elegida con sus provincias; íconos de estados de emergencia según el motivo; casos de la Defensoría; burbujas de empresas por provincia | `garita/geo.py` | `capa_departamentos`, `mapa_region`, `_icono_emergencia`, `centroide`, `distancia_km` |
| 06.4 Mapa en la app con selector de región | `app.py` | pestaña 2 |

## 05 · Dashboards (Streamlit)

| Subcategoría | Archivo | Función |
|---|---|---|
| 05.1 Página: configuración, estilos y estado de la sesión | `app.py` | — |
| 05.2 Barra lateral: modo de la app y fechas de corte | `app.py` | — |
| 05.3 Pestaña 1: el pedido (texto libre y detalle) | `app.py` | — |
| 05.4 Pestaña 2: mapa de riesgo por región (cualquier región del Perú) | `app.py` | — |
| 05.11 Callbacks: interpretar el pedido y llevar la región al pedido sin que los campos retrocedan | `app.py` | `_interpretar`, `_usar_region` |
| 05.12 Tarjetas de la región: delitos, conflictos, emergencias y empresas | `app.py` | — |
| 05.13 Gráfico: la región frente a las otras 24 | `app.py` | — |
| 05.5–05.6 Pestaña 3: lista corta y gráfico del desglose del puntaje | `app.py` | — |
| 05.7–05.8 Pestaña 4: benchmark, piso legal, evaluación de una oferta y gráfico de contratos | `app.py` | — |
| 05.9 Pestaña 5: documentos y calendario de vencimientos | `app.py` | — |
| 05.10 Pestaña 6: solicitud de propuesta en Word y Excel | `app.py` | — |

## 04 · MCP ("Garita para Claude")

| Subcategoría | Archivo | Función |
|---|---|---|
| 04.1 Servidor: nombre, instrucciones y anotaciones de solo lectura | `mcp_server/server.py` | `mcp = FastMCP("garita")`, `SOLO_LECTURA` |
| 04.2 Consulta de empresas autorizadas y su ficha | `mcp_server/server.py` | `buscar_empresas`, `ficha_empresa` |
| 04.3 Salidas: DataFrame a JSON (fechas ISO, NaN → None) y validación de entradas | `mcp_server/server.py` | `_valor`, `_registros`, `_sin_datos`, `_departamento`, `_modalidad`, `_armas`, `_ruc` |
| 04.4 Precio: contratos, benchmark, piso legal y semáforo de una oferta | `mcp_server/server.py` | `contratos_vigilancia`, `benchmark_precio`, `costo_laboral_minimo`, `evaluar_oferta` |
| 04.5 Contexto: riesgo de la zona y puntaje de confianza | `mcp_server/server.py` | `riesgo_zona`, `puntaje_confianza` |
| 04.6 Arranque por stdio | `mcp_server/server.py` | `mcp.run()` |
| 04.7 Pruebas con tablas sintéticas y cliente en memoria | `tests/test_mcp.py` | `test_*` |
| Configuración del proyecto y plugin instalable | `.mcp.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | — |

## 16 · Skills de Claude Code

| Subcategoría | Archivo | Función |
|---|---|---|
| Skill del producto: método para evaluar proveedores | `skills/evaluar-proveedor-seguridad/SKILL.md`, `reference.md` | — |
| 16.1–16.3 Cálculo de una oferta y estimado del pedido | `skills/evaluar-proveedor-seguridad/scripts/precio_puesto.py` | `calcular` |
| Desarrollo: actualizar los datos | `.claude/skills/actualizar-datos/SKILL.md` | — |
| 16.4 Desarrollo: regenerar el benchmark y resumir costos | `.claude/skills/regenerar-benchmark/` | `resumen_benchmark.py` |
| 16.5–16.6 Desarrollo: revisar secretos antes del push | `.claude/skills/revisar-secretos/` | `revisar_secretos.py` |
| 16.7 Desarrollo: preparar el demo | `.claude/skills/preparar-demo/` | `chequeo_demo.py` |

## Lógica propia de Garita (no es una herramienta del curso)

| Subcategoría | Archivo | Función |
|---|---|---|
| G.1 Puntaje de confianza: siete componentes con peso, nivel y fuente | `garita/confianza.py` | `puntaje_confianza` |
| G.2 Lista corta ordenada por puntaje y cercanía | `garita/confianza.py` | `lista_corta` |
| Acceso único a los datos procesados (app, MCP y skill) | `garita/datos.py` | `buscar_empresas`, `ficha_empresa`, `benchmark`, `riesgo_zona`, `estados_emergencia`, `ranking_regiones`, `provincias_region`, `empresas_por_provincia` |
| Pedido y solicitud de propuesta | `garita/pedido.py` | `Pedido`, `solicitud_docx`, `solicitud_xlsx`, `calendario_ics` |
| Orquestador del pipeline | `run_pipeline.py` | `main` |

## Qué paso del pipeline usa qué skill

| Paso del pipeline | Comando | Skill que lo dispara |
|---|---|---|
| sucamec, oece, sunat, proveedores, geo, defensoria, documentos, metadatos | `uv run python run_pipeline.py` | `/actualizar-datos` |
| documentos, extraer, benchmark (gasta tokens, con tope) | `uv run python run_pipeline.py --pasos documentos,extraer,benchmark` | `/regenerar-benchmark` |
| Antes de cada push | `revisar_secretos.py` | `/revisar-secretos` |
| Antes de presentar | `chequeo_demo.py` | `/preparar-demo` |
| Evaluar propuestas desde Claude | MCP `garita` + `precio_puesto.py` | `evaluar-proveedor-seguridad` |
