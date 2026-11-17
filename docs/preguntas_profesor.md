# Preguntas probables sobre el código y dónde está cada respuesta

Busca el número de sección (por ejemplo `03.2`) en el repo para llegar directo al código.

## Datos y scraping (herramienta 03)

| Pregunta | Respuesta corta | Dónde |
|---|---|---|
| ¿Cómo sacas las empresas de SUCAMEC si la página no tiene la tabla? | El registro es un formulario JSF/PrimeFaces: abro la página, guardo la cookie y el `javax.faces.ViewState`, y replico el POST AJAX del botón Buscar y del paginador con los mismos nombres de campo que envía el navegador. | `garita/sucamec.py` · 03.1 y 03.2 (`FormularioSucamec.buscar`, `.pagina`) |
| ¿Por qué consultas departamento por departamento? | Porque el buscador corta en 2,000 resultados: vigilancia con armas a nivel nacional da exactamente 2,000, y sumando los departamentos son 2,249. | `garita/sucamec.py` · docstring y `TOPE_BUSCADOR` |
| ¿Cómo sabes si una empresa está autorizada con o sin armas? | El texto no siempre lo dice; el formulario sí tiene ese filtro, así que consulto con armas y sin armas por separado y cada fila hereda la etiqueta. | `garita/sucamec.py` · 03.3 `limpiar` |
| ¿De dónde salen los contratos? | API OCDS del OECE (la misma del HW3): ZIP mensuales de 22 CSV; uno siete tablas en una fila por proceso (ocid). | `garita/oece.py` · 03.5 y 03.6 |
| ¿Cómo filtras vigilancia sin traer cámaras o uniformes? | Por la clasificación CUBSO del ítem ("SERVICIO DE SEGURIDAD Y VIGILANCIA"), y el título solo como respaldo con lista de exclusiones. | `garita/oece.py` · docstring y 03.6; `config.yaml → oece` |
| ¿Qué es un ocid? ¿Release o record? | El ocid es el proceso completo; un release es una novedad; un record es la foto compilada. Los bulk mensuales son records: una fila por ocid. | `garita/oece.py` (heredado del HW3) |
| ¿Cómo sabes si una empresa tiene penalidades o está inhabilitada? | Ficha JSON pública del buscador de proveedores del OECE por RUC: `esAptoContratar`, penalidades y sanciones. "No apto" casi siempre es RNP vencido, no sanción: así lo digo. | `garita/oece.py` · 03.8; `garita/confianza.py` · G.1 |
| ¿Por qué no consultas SUNAT por RUC? | La consulta web responde 403 y pide captcha. Uso el padrón reducido público (395 MB) leído línea por línea, solo RUC 20. | `garita/sunat.py` · 03.10 y 03.11 |
| ¿No te bloquean? | Pausa entre peticiones, reintentos con espera creciente y caché: nada se descarga dos veces. | `garita/red.py` · 03.0 |

## LLM con salidas estructuradas (herramienta 08)

| Pregunta | Respuesta corta | Dónde |
|---|---|---|
| ¿Qué le pides exactamente al LLM? | Que lea los TDR de las Bases y devuelva puestos (cantidad, horas, días, armado), plazo, supervisor, perfil y una cita textual de evidencia. | `garita/extraccion.py` · 08.7 `SISTEMA_TDR` |
| ¿Cómo garantizas que devuelva JSON? | `response_format={"type": "json_object"}` y validación con Pydantic; si no valida, le devuelvo el error una vez; si vuelve a fallar, el proceso queda fuera del benchmark. | `garita/llm.py` · 08.4 `estructurado`; `garita/esquemas.py` · 08.1 |
| ¿Por qué en La Libertad sale el precio nacional? | Tiene 3 contratos válidos y con menos de 5 uno caro mueve la mediana un 60 %; se usa el rango nacional (75 contratos) y la app lo dice. | `garita/datos.py` `benchmark`, `MIN_CONTRATOS_DEPARTAMENTO` |
| ¿El LLM calcula el precio? | No. El LLM solo lee; Python divide monto ÷ (puestos 24/7 equivalentes × meses). El monto y el plazo vienen del contrato firmado en el OECE, no del LLM. | `garita/benchmark.py` · 08.5 `construir`, `precio_puesto_mes` |
| ¿Qué es un puesto 24/7 equivalente? | Un puesto de 12 h vale 0.5; uno de 8 h, 1/3; se ajusta por días a la semana. | `garita/extraccion.py` `_fila_extraccion`; `garita/benchmark.py` `puestos_equivalentes_24h` |
| ¿Cuánto cuesta y cómo controlas el gasto? | Cada llamada se registra con tokens, latencia y costo según la franja horaria de DeepSeek; antes de cada llamada se verifica el tope `GARITA_TOPE_USD`. | `garita/costos.py` · 08.6; `logs/costos.csv` |
| ¿Qué pasa si no hay clave o se cae la API? | La app usa reglas (regex) para el pedido y los documentos, y lee los datos ya procesados. Nunca se cae. | `garita/pedido.py` · 08.10 y 08.11; `app.py` · 05.2 |
| ¿Cómo sabes que el LLM lee bien? | Lo comparo con una línea base de reglas: cobertura, % de precios plausibles y dispersión; más una muestra de 15 para auditoría humana. Cada extracción guarda su evidencia. | `eval/evaluar_extraccion.py` · 12.1–12.3; `eval/resultados/` |

## Document AI (10)

| Pregunta | Respuesta corta | Dónde |
|---|---|---|
| ¿Pasas todas las páginas por OCR? | No: triaje como en la sesión 10. Página con capa de texto → extracción directa; página imagen → OCR, con tope de 8 por PDF. | `garita/documentos.py` · 10.2 `triaje` |
| ¿Cómo encuentras los términos de referencia en 60–140 páginas? | Puntúo cada página por palabras del servicio y tomo el bloque de 14 páginas seguidas con más puntaje. Primero probé buscar el título y fallaba por el OCR viejo. | `garita/documentos.py` · 10.3 `leer_tdr` |
| ¿Por qué RapidOCR y no PaddleOCR? | PaddleOCR (sesión 10) en local; en Streamlit Cloud Paddle no cabe en 1 GB, así que corren los mismos modelos PP-OCR en ONNX con RapidOCR. | `garita/documentos.py` · 10.1 `motor_ocr` |
| ¿Cómo lees el reporte de la Defensoría? | PyMuPDF + regex: el Cuadro 3 (conflictos por región) y los bloques "Caso / Tipo / Ubicación" para ubicar casos por provincia. El número del reporte se lee del contenido, no del nombre del archivo. | `garita/defensoria.py` · 10.5 a 10.7 |

## Mapas (06) y app (05)

| Pregunta | Respuesta corta | Dónde |
|---|---|---|
| ¿De dónde salen los delitos del mapa? | Excel del índice temático de Delitos del INEI, con las denuncias del SIDPOL de la PNP: número y tasa por 10 mil habitantes, 2024. No hay serie oficial descargable por provincia, por eso los delitos van por región y lo provincial son empresas, emergencias y casos. | `garita/delitos.py` · 03.14 a 03.16 |
| ¿Qué significan los íconos del mapa? | Rombo rojo: estado de emergencia por minería ilegal; mira: crimen organizado; hoja: narcotráfico; fuego: casos de la Defensoría; burbuja naranja: empresas con sede autorizada (tamaño ∝ √n); estrella: el sitio del cliente. | `garita/geo.py` · 06.3 `mapa_region`, `_icono_emergencia` |
| ¿Por qué antes "retrocedían" los números al subir la estatura? | Los widgets se creaban con `value=` del valor anterior: cada clic los volvía widgets nuevos. Ahora cada uno tiene clave fija en `st.session_state` y el botón escribe por callback. | `app.py` · 05.1 `CLAVES` y 05.11 |
| ¿De dónde salen las provincias? | Disuelvo los 1,834 distritos de la sesión 06 por (departamento, provincia) con GeoPandas y simplifico la geometría. | `garita/geo.py` · 06.1 |
| ¿Cómo calculas la distancia de la sede al sitio? | Centroide del distrito de la sede (calculado en UTM 18S) y haversine; es línea recta. | `garita/geo.py` `centroide`, `distancia_km` |
| ¿Cómo se calcula el puntaje de confianza? | Siete componentes con peso en `config.yaml` (autorización 30, vigencia 10, SUNAT 15, registro de proveedores 15, penalidades 10, experiencia 15, cobertura 5), cada uno con nivel y fuente. | `garita/confianza.py` · G.1 |
| ¿De dónde sale el piso legal? | RMV S/ 1,230 (DS 015-2026-TR) + recargo nocturno 35% en 1/3 de las horas + EsSalud, SCTR, Vida Ley + gratificaciones, CTS y vacaciones; 3.8 agentes por puesto 24/7; 10% de margen mínimo. | `garita/benchmark.py` · `costo_laboral_minimo`; `config.yaml → costo_laboral` |
| ¿Qué armas puede pedir el cliente? | Las del Reglamento de la Ley 30299 (DS 010-2017-IN, art. 19): revólver .38 SPL, pistola hasta 9x17 mm, escopeta y carabina solo fuera del radio urbano. Un calibre mayor a 9x17 mm no se permite en vigilancia privada (art. 19.2) y la app lo marca en rojo. | `garita/pedido.py` `ARMAS`, `avisos_armamento` |
| ¿Usas datos de personas? | No. Solo empresas. El perfil (estatura, edad) es un requisito del cliente. Del padrón de SUNAT solo RUC 20. | `README.md` · Datos y privacidad; `garita/pedido.py` docstring |

## MCP (04) y skills (16)

| Pregunta | Respuesta corta | Dónde |
|---|---|---|
| ¿Para qué un MCP si ya tienes la app? | Para que un analista use los mismos datos desde Claude: el MCP pone los datos, la skill pone el método. Es otro canal del producto. | `mcp_server/server.py` · 04.1; `skills/evaluar-proveedor-seguridad/SKILL.md` |
| ¿El MCP duplica lógica? | No: las 8 herramientas llaman a `garita/datos.py` y `garita/benchmark.py`, igual que la app. | `mcp_server/server.py` · 04.2 a 04.5 |
| ¿Cómo se instala? | `/plugin marketplace add josemigueldiaz1/Garita-StartupProject` y `/plugin install garita@garita`; en este repo `.mcp.json` ya lo registra. | `.claude-plugin/`, `.mcp.json` |
| ¿Qué skills de desarrollo hay y cuándo se usan? | actualizar-datos, regenerar-benchmark (gasta tokens: solo a mano), revisar-secretos (antes del push) y preparar-demo. | `.claude/skills/`; `docs/mapa_herramientas.md` · último cuadro |

## Si piden cambiar algo en vivo

| Pedido | Qué tocar |
|---|---|
| "Cambia el peso de la autorización a 40" | `config.yaml → confianza.pesos.autorizacion_sucamec`; la app recalcula |
| "Sube la RMV a S/ 1,300" | `config.yaml → costo_laboral.rmv`; cambia el piso legal y la alerta |
| "Agrega otro mes de contratos" | `config.yaml → oece.meses` y `uv run python run_pipeline.py --pasos oece` |
| "Muestra solo empresas con sede en la provincia" | Ya existe el filtro en la pestaña 3 (`app.py` · 05.5) |
