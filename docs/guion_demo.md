# Guion de la presentación (3 minutos)

**Caso del demo:** "vigilancia con armas, 8 puestos 24/7, campamento minero en Pataz, La Libertad".

Las cifras entre `<< >>` se completan con los datos procesados antes del ensayo final.

## Antes de entrar (7:25 a. m.)

- [ ] Abrir la app en la URL pública **10 minutos antes**: Streamlit Community Cloud apaga las apps sin uso y tarda en despertar.
- [ ] Dejar abierta la pestaña "1 · Pedido" con el caso de Pataz ya cargado y el navegador en zoom 110 %.
- [ ] Tener en otra pestaña el video de respaldo (plan B) y en el escritorio el PDF de la carta fianza sintética (`data/demo/`).
- [ ] Cerrar notificaciones, WhatsApp y correo. Probar compartir pantalla.
- [ ] Cronómetro visible.

## 0:00 – 0:30 · El problema

**Qué decir:**

> "Una minera en Pataz necesita 8 puestos de vigilancia armada las 24 horas. Hoy, el jefe de seguridad tiene que entrar al registro de SUCAMEC empresa por empresa, revisar SUNAT por separado y comparar cotizaciones sin saber cuánto cuesta realmente un puesto. Si elige una empresa barata porque no paga planilla, el problema laboral y el de seguridad terminan siendo suyos. Y en Pataz, con la violencia de la minería ilegal, equivocarse cuesta caro. Garita resuelve eso en un minuto."

**Qué hacer:** nada en pantalla todavía; la app está en "1 · Pedido".

## 0:30 – 2:30 · Demo en vivo

| Tiempo | Pestaña | Qué hacer | Qué decir |
|---|---|---|---|
| 0:30 – 0:50 | **1 · Pedido** | Mostrar el pedido cargado: La Libertad, Pataz, campamento minero, 8 puestos 24/7, con armas. Señalar los requisitos de perfil y equipamiento | "El cliente define su pedido: lugar, puestos, horario, armamento y el perfil del personal. Lo que exige el cliente sobre el personal se pide como declaración de la empresa; nunca guardamos datos de vigilantes." |
| 0:50 – 1:10 | **2 · Riesgo de la zona** | Señalar Pataz en el mapa y el número de conflictos de la provincia | "Con el reporte de la Defensoría del Pueblo, Garita ubica cada conflicto por provincia. Pataz tiene `<<N_CONFLICTOS_PATAZ>>` casos registrados; por eso recomienda vigilancia armada y supervisión." |
| 1:10 – 1:45 | **3 · Proveedores** | Mostrar la lista corta; abrir la primera empresa y su desglose del puntaje | "De `<<N_EMPRESAS_SUCAMEC>>` empresas en el registro, solo `<<N_LA_LIBERTAD_ARMAS>>` tienen autorización vigente con armas en La Libertad. Cada punto del puntaje dice de dónde sale: SUCAMEC, SUNAT y el OECE, con su link. Esta autorización vence el `<<FECHA>>`, y Garita lo avisa." |
| 1:45 – 2:10 | **4 · Precio** | Mostrar el rango del benchmark; escribir una oferta por debajo del piso legal y mostrar la alerta roja | "Este es el insight: los contratos públicos de vigilancia dicen '12 agentes, 2 turnos' en texto libre. Un LLM los convierte en puestos y meses, y por primera vez hay un precio por puesto-mes comparable: mediana de `<<MEDIANA_PUESTO_MES>>` soles con `<<N_CONTRATOS>>` contratos. Esta oferta está por debajo del costo laboral mínimo: no cierra pagando planilla." |
| 2:10 – 2:20 | **5 · Documentos** | Subir la carta fianza sintética y mostrar el monto y la fecha de vencimiento extraídos | "El proveedor sube su carta fianza y Garita lee el monto y la fecha de vencimiento. Este documento es sintético y así lo marca la app." |
| 2:20 – 2:30 | **6 · Solicitud de propuesta** | Clic en descargar la solicitud (Word o Excel) | "Todo el pedido sale en una solicitud de propuesta lista para enviar a las empresas de la lista corta." |

**Si vas atrasado:** en 1:45 salta "5 · Documentos" y ve directo a "6 · Solicitud de propuesta".

## 2:30 – 3:00 · El negocio

**Qué decir:**

> "Cobramos S/ 1,500 al mes a la empresa que contrata seguridad: mineras medianas, plantas y puertos. Cada consulta nos cuesta menos de un décimo de centavo de dólar en tokens y el servidor es casi gratis. Después vienen una comisión de 3 a 5 % cuando intermediamos el contrato y un perfil premium para las empresas de seguridad que quieran mostrarse verificadas. Garita también funciona dentro de Claude, con un servidor MCP y una skill. Lo siguiente: tres pilotos con mineras medianas en La Libertad."

Cortar a las 3:00 en punto. Si sobra tiempo, no improvisar: decir "Gracias" y esperar las preguntas.

## Plan B: si se cae el despliegue o internet

1. Decir: "Se cayó la conexión; muestro el video del software funcionando, grabado con el mismo código del repo."
2. Abrir el video de respaldo (60 a 90 segundos): `<<URL_VIDEO>>`.
3. Mientras corre, narrar el mismo guion de arriba.
4. Si hay tiempo, correr la app en local: `uv run streamlit run app.py`.

## Si falla la API del LLM (modo demo)

- La app sigue funcionando: el riesgo, la lista de proveedores, el puntaje y el benchmark salen de los datos ya procesados en `data/processed/`. El LLM solo se usa en el pipeline y para leer documentos nuevos.
- La app muestra un aviso de "modo demo". Decir: "La API no responde en este momento; la app sigue en modo demo con los datos ya procesados, que es justamente para lo que está diseñada."
- En "5 · Documentos", usar el resultado precargado de la carta fianza sintética.

## Preguntas probables en los comentarios

Ver `docs/preguntas_profesor.md` (archivo, función y sección del código para cada respuesta).
