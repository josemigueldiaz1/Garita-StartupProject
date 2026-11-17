# Borrador de las partes 2, 3, 4, 5 y 7 del README (y opcionales)

> Borrador para integrar al `README.md`. Las cifras entre `<< >>` salen de los datos procesados o de los logs de costos y se completan antes de la entrega. Lo marcado como **estimado** o **dato antiguo** debe seguir marcado así en el README final.

---

## 2. Founder

<<FOUNDER>>

> Pendiente: 2 o 3 líneas de José Miguel Díaz: carrera y ciclo en la Universidad del Pacífico, vínculo con minería, puertos o seguridad (familia, prácticas, región), y por qué es la persona indicada para este problema.

---

## 3. Problema

**Quién lo sufre.** El jefe de seguridad patrimonial o de compras de una minera mediana, una planta industrial o un puerto que tiene que contratar vigilancia para una operación, a veces en una zona de alto riesgo. Del otro lado, las empresas de seguridad formales, que pierden contratos contra ofertas que no cubren el costo laboral.

**Cómo lo resuelve hoy.**

1. Pide cotizaciones a las empresas que ya conoce o que le recomendaron. La contratación de servicios corporativos en el Perú depende del «boca a boca», de grupos de WhatsApp y de contactos personales ([Infomercado](https://infomercado.pe/bilda-consolida-su-plataforma-b2b-de-servicios-especializados-y-busca-impulsar-la-contratacion-industrial-en-el-peru/)).
2. Verifica a mano, empresa por empresa, la autorización en el [registro de SUCAMEC](https://www.sucamec.gob.pe/rgGSSP/aplicacion/resoluciones/List.xhtml): si está vigente, para qué modalidad (con o sin armas) y en qué departamento. Por separado revisa SUNAT y, si quiere, el buscador de proveedores del OECE.
3. Compara precios sin una referencia: no sabe si una oferta barata es eficiente o si es barata porque no paga planilla.
4. Si es una minera grande, exige además una homologación anual hecha por un tercero (ver [competencia](competencia.md)).

**Cuánto le cuesta.**

- **El riesgo legal y laboral.** La vigilancia y la seguridad son actividades complementarias que se tercerizan mediante intermediación laboral ([La Cámara](https://lacamara.pe/reglas-basicas-de-la-intermediacion-laboral/)). La empresa de servicios debe dar una fianza que garantice los derechos de sus trabajadores, y si esa fianza no alcanza, la empresa usuaria responde solidariamente por los adeudos laborales ([Ley 27626, arts. 24 y 25](https://lpderecho.pe/ley-intermediacion-laboral-ley-27626/)). Contratar a la empresa equivocada puede terminar en una deuda propia.
- **El riesgo de seguridad.** Una empresa sin autorización vigente para armas, o sin personal formal, falla justo donde más se necesita. En Pataz, la minería ilegal mantiene un estado de emergencia, ataques a operaciones mineras y secuestros de trabajadores ([ProActivo](https://proactivo.com.pe/a-pesar-del-estado-de-emergencia-y-presencia-policial-inseguridad-y-violencia-se-agravan-en-pataz-con-secuestro-de-mineros/), [Andina](https://andina.pe/agencia/noticia-gobierno-intensificara-operativos-contra-mineria-ilegal-tras-hechos-violencia-pataz-1057857.aspx)).
- **El tiempo.** Verificar cada proveedor contra tres fuentes y comparar cotizaciones toma días del equipo de seguridad o de compras. La medición de cuánto exactamente es uno de los objetivos de las conversaciones con usuarios.
- **La informalidad del sector.** SUCAMEC aprobó en 2024 un programa de seguridad privada que responde a la informalidad de las empresas del sector ([SUCAMEC](https://cdn.www.gob.pe/uploads/document/file/6797087/5885641-programa-de-seguridad-privada-2024.pdf)), y el Ministerio de Trabajo reconoce la informalidad laboral en la vigilancia ([Andina](https://andina.pe/ingles/noticia-ministerio-trabajo-busca-formalizar-sector-vigilancia-720871.aspx)). No encontramos una cifra oficial actual del porcentaje de informalidad.

**Evidencia de usuarios.** Las notas de las 3 conversaciones están en [`docs/research/`](research/README.md), con la guía y la plantilla usadas. <<RESUMEN_CONVERSACIONES>>

---

## 4. Solución e insight

**La solución.** Garita es una app web donde el cliente describe su necesidad (lugar, puestos, horario, armamento, perfil y equipamiento) y en un minuto recibe:

1. El **riesgo de la zona** por provincia, con los conflictos sociales registrados por la Defensoría del Pueblo.
2. Una **lista corta de empresas con autorización vigente de SUCAMEC** para esa modalidad y ese departamento, cada una con un **puntaje de confianza de 0 a 100** que muestra de qué se compone: autorización y vigencia (SUCAMEC), estado y condición del RUC (SUNAT), inhabilitaciones, penalidades y contratos públicos ganados (OECE). Cada dato dice si es verificado, extraído, declarado o sintético.
3. Un **rango de precio por puesto-mes** en su departamento y una alerta cuando una oferta queda por debajo del costo laboral mínimo de un puesto 24/7.
4. La lectura de **cartas fianza y pólizas** para sacar montos y fechas de vencimiento.
5. Una **solicitud de propuesta** exportable para enviar a la lista corta.

**El insight.** El precio de un puesto de vigilancia sí es público, pero está escondido. El Estado contrata cientos de servicios de vigilancia al año y publica cada contrato en el portal de contrataciones abiertas del OECE, con su monto y sus Bases. Lo que nadie ha hecho es leerlos: las Bases dicen "12 agentes, 2 turnos, 365 días" en texto libre, muchas veces escaneado. Garita las lee con OCR y un LLM con salida estructurada, las convierte en puestos, horas y meses, y con eso calcula por primera vez un **precio por puesto-mes comparable**: mediana de **<<MEDIANA_PUESTO_MES>>** soles, a partir de **<<N_CONTRATOS>>** contratos. El mismo dato que sirve al comprador para no pagar de más sirve para detectar ofertas que solo cierran sin planilla.

**El segundo insight:** la confianza no depende de un solo registro. Una empresa puede estar autorizada en SUCAMEC pero estar inhabilitada para contratar con el Estado, o con su RUC no habido. Cruzar las tres fuentes por RUC es simple con código y lento a mano.

---

## 5. Why now

- **Los datos ya son abiertos y legibles por máquina.** El OECE publica los contratos del Estado en el estándar OCDS con descargas mensuales, y SUCAMEC mantiene en línea su registro de empresas autorizadas con fecha de vencimiento ([SUCAMEC](https://www.gob.pe/institucion/sucamec/pages/9498-empresas-de-seguridad)). Hace pocos años esa información estaba en PDF o en ventanilla.
- **Leer documentos dejó de ser caro.** Hace tres años, extraer puestos y turnos de cientos de Bases escaneadas exigía entrenar un modelo o pagar a una persona. Hoy un LLM con salida JSON lo hace por centavos: todo el benchmark costó <<COSTO_PIPELINE>> en llamadas a la API.
- **La seguridad privada es más crítica que nunca en las zonas mineras.** En agosto de 2026 la Defensoría del Pueblo registró 188 conflictos sociales (138 activos y 50 latentes), y 102 tuvieron al menos un hecho de violencia ([Defensoría](https://www.defensoria.gob.pe/defensoria-del-pueblo-en-agosto-se-registraron-188-conflictos-sociales-a-nivel-nacional/)). En junio de 2026 había 151 conflictos activos, 96 de ellos socioambientales ligados a la minería ([Reporte Minero](https://www.reporteminero.cl/noticia/noticias/2026/08/peru-cartera-minera-64-mil-millones-conflictos-socioambientales-canon)). En Pataz, el Estado mantiene operaciones contra la minería ilegal con incautación de armas y explosivos ([El Peruano](https://elperuano.pe/noticia/295395-operacion-aguila-dorada-incauta-arsenal-de-guerra-y-material-explosivo-en-pataz)).
- **El costo laboral acaba de subir.** La remuneración mínima vital pasó de S/ 1,130 a S/ 1,230 el 1 de octubre de 2026 y tiene un segundo tramo pendiente hasta S/ 1,300 ([DS 015-2026-TR](https://busquedas.elperuano.pe/dispositivo/EX/2559163-1), [El Peruano](https://elperuano.pe/noticia/305675-gobierno-oficializa-aumento-del-sueldo-minimo-vital-subira-a-s1230-a-partir-del-1-de-octubre)). Cada alza mueve el piso legal de un puesto 24/7 y vuelve obsoletas las cotizaciones viejas: es el momento en que un comprador necesita saber qué precio todavía cubre la planilla.
- **El sector es grande y está fragmentado.** SUCAMEC reportaba 4,319 empresas acreditadas y más de 125,000 agentes autorizados ([El Peruano](https://elperuano.pe/noticia/141085-sucamec-acredito-a-mas-de-125-mil-agentes-de-seguridad-en-todo-el-pais); **dato antiguo**: la nota no muestra fecha y una nota de prensa de EULEN de marzo de 2022 cita la misma cifra de agentes, [EULEN](https://www.eulen.com/cl/wp-content/uploads/sites/5/2022/11/06-Nota-de-prensa-Perfiles-de-agente-de-seguridad.pdf)). Garita cuenta hoy <<N_EMPRESAS_SUCAMEC>> empresas con autorización en el registro.

---

## 7. Modelo de negocio

**Quién paga.** La empresa que contrata seguridad: mineras medianas, plantas industriales y puertos. No el proveedor de seguridad, para que la recomendación sea neutral.

**Precio concreto.**

| Producto | Precio | Qué incluye |
|---|---|---|
| Garita Empresa | **S/ 1,500 al mes** por empresa compradora | Verificación de proveedores, benchmark de precios, riesgo por zona, lectura de documentos, alertas de vencimiento y solicitudes de propuesta ilimitadas |
| Comisión (etapa 2) | 3 % a 5 % del contrato cuando Garita intermedia la contratación | Gestión de la convocatoria y del contrato |
| Perfil premium (etapa 2) | Suscripción para empresas de seguridad | Perfil verificado, documentos al día y aparición destacada, **sin alterar el puntaje** |

Ejemplo de la comisión: un contrato de 8 puestos 24/7 a la mediana de <<MEDIANA_PUESTO_MES>> soles por puesto-mes durante 12 meses vale 8 × 12 × <<MEDIANA_PUESTO_MES>> soles; el 3 % de ese contrato es la comisión.

**Costo por usuario.**

| Concepto | Costo | Fuente |
|---|---|---|
| Tokens por consulta del usuario | <<TOKENS_POR_CONSULTA>> tokens, entre US$ 0.0003 y US$ 0.0012 por llamada a `deepseek-chat` | Logs de `logs/costos.csv`; referencia: en el HW3 del autor, 32 llamadas costaron US$ 0.013 en total |
| Uso típico de un cliente al mes (**estimado**) | 4 procesos de contratación × unas 6 llamadas (documentos y resumen) = 24 llamadas ≈ US$ 0.03 al mes en el peor caso | Supuesto a validar con usuarios |
| Normalización de contratos (pipeline) | <<COSTO_PIPELINE>> por corrida, una vez al mes, compartido entre todos los clientes | `logs/costos.csv` |
| Servidor del demo | US$ 0: Streamlit Community Cloud | |
| Servidor en producción (**estimado**) | Una máquina virtual pequeña, del orden de US$ 20 a US$ 40 al mes, compartida entre clientes | Estimado |

Con S/ 1,500 al mes por cliente, el costo variable en tokens es menor al 0.1 % del precio. El costo real del negocio es la venta y la actualización de los datos, no el cómputo.

---

## Opcionales

### Mercado (TAM, SAM y SOM)

Todas las cifras son **estimadas** y sus supuestos están a la vista.

| Nivel | Cifra | Supuesto |
|---|---|---|
| TAM: gasto en seguridad privada en el Perú | Entre US$ 400 millones y US$ 1,400 millones al año (**dato antiguo**, estimaciones del sector) | US$ 400 millones según EULEN Perú en 2021 ([Infomercado](https://infomercado.pe/peru-sector-seguridad-mueve-mas-de-400-millones-de-dolares-en-el-pais/)); US$ 1,400 millones según Prosegur en 2018 ([Prosegur](https://www.euroamerica.org/wp-content/uploads/2018/06/LopezMartin_Prosegur_PPT_Peru-UE2018.pdf)). No hay una cifra oficial reciente |
| SAM: suscripciones de empresas compradoras con proceso formal | S/ 36 millones al año (**estimado**) | 2,000 empresas medianas y grandes que contratan vigilancia con un proceso formal (minería, puertos, plantas, retail) × S/ 18,000 al año. El número de empresas es un supuesto a validar |
| SOM: lo alcanzable en 3 años | S/ 720 mil al año (**estimado**) | 40 clientes (2 % del SAM), empezando por mineras medianas de La Libertad, Cajamarca y Arequipa |

### Competencia

Resumen de [`docs/competencia.md`](competencia.md): las homologadoras (SGS, Bureau Veritas, Achilles) y las plataformas de gestión de contratistas (eGestiona, Subcontrataley) evalúan al proveedor una vez al año o gestionan sus documentos, y el registro de SUCAMEC se consulta una empresa a la vez. Ninguna ofrece un precio de referencia por puesto-mes ni cruza al proveedor con el riesgo de la zona. Ese es el vacío que cubre Garita.

### Cómo conseguir los primeros usuarios

1. Las 3 conversaciones de `docs/research/`: cada una termina pidiendo una presentación a otra persona.
2. Mineras medianas de La Libertad (Pataz) y Cajamarca, donde el riesgo es más alto y no hay un área de homologación grande.
3. Un reporte gratuito y público del benchmark de precios por departamento, como gancho para jefes de compras.
4. "Garita para Claude": el servidor MCP y la skill permiten que un analista de compras use los mismos datos desde su asistente.

### Roadmap

| Etapa | Qué |
|---|---|
| Ahora (demo) | Verificación SUCAMEC + SUNAT + OECE, benchmark de precios, riesgo por provincia, lectura de documentos, solicitud de propuesta, MCP y skill |
| 3 meses | Pilotos con 3 mineras medianas; sanciones de SUCAMEC y SUNAFIL; alertas de vencimiento por correo o Telegram |
| 6 meses | Centrales de riesgo privadas (deudas), perfiles declarados por las empresas de seguridad, actualización mensual automática |
| 12 meses | Intermediación del contrato con comisión; otros sectores (puertos, condominios, retail); otros servicios tercerizados con registro público |

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Las fuentes públicas cambian su formato (SUCAMEC es un formulario JSF) | Los datos procesados quedan versionados; la app sigue en modo demo; un fallo del scraper se detecta en la actualización mensual |
| El LLM lee mal una Bases | Cada extracción guarda su evidencia y su página; se mide contra una línea base de reglas fijas; los datos extraídos se marcan como "extraído", no como "verificado" |
| Los precios públicos no reflejan los precios privados | Se presenta como referencia, no como precio de mercado único; se complementa con cotizaciones declaradas por los clientes |
| Las mineras compran por relaciones | Entrada por mineras medianas y por el benchmark, que nadie ofrece |
| Datos personales | Solo se procesan datos de empresas; nunca de vigilantes |

### Cuánto pediríamos a un inversionista (**propuesta**)

US$ 120,000 de pre-semilla para 12 meses: dos personas a tiempo completo (producto y ventas), infraestructura de datos, revisión legal y tres pilotos pagados con mineras medianas. El objetivo es llegar a 15 clientes pagando antes de la siguiente ronda.
