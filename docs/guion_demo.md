# Guion de la presentación (3 minutos)

**App:** https://garita-seguridad.streamlit.app/
**Caso del demo:** "Necesito vigilancia con armas, 8 puestos 24/7 para un campamento minero en Pataz, La Libertad, por 12 meses. Con radios y control de accesos." (ya viene escrito en la pestaña 1).

## Antes de entrar (7:10 a 7:25 a. m.)

- [ ] **7:10** Abrir la app. Si aparece "Yes, get this app back up", hacer clic y esperar a que cargue: Streamlit Cloud duerme las apps sin uso.
- [ ] **7:11** Abrir la pestaña "2 · Mapa de riesgo" una vez para que el mapa quede en caché.
- [ ] **7:12** Precalentar el OCR: pestaña "5 · Documentos" → "Usar la versión escaneada 🧪". La primera vez tarda ~30 s porque carga el modelo; después queda en memoria y en la demo responde en segundos.
- [ ] **7:15** Recargar la página (F5) para empezar limpio en "1 · Pedido". Zoom del navegador al 110 %.
- [ ] Tener en otra pestaña el video de respaldo y, en una terminal, la app local lista (`uv run streamlit run app.py`).
- [ ] Cerrar notificaciones, WhatsApp y correo. Probar compartir pantalla. Cronómetro visible.

## 0:00 – 0:30 · El problema

> "Una minera en Pataz necesita 8 puestos de vigilancia armada las 24 horas. Hoy, el jefe de seguridad elige por recomendación, entra al registro de SUCAMEC empresa por empresa, revisa SUNAT por separado y compara cotizaciones sin saber cuánto cuesta de verdad un puesto. Si contrata a una empresa barata porque no paga planilla, la deuda laboral también le cae a la minera, por ley. Y en Pataz, que está en estado de emergencia por la minería ilegal, equivocarse cuesta caro. Garita resuelve esto en un minuto, con datos oficiales."

## 0:30 – 2:30 · Demo en vivo

| Tiempo | Pestaña | Qué hacer | Qué decir |
|---|---|---|---|
| 0:30 – 0:45 | **1 · Pedido** | Clic en **Interpretar pedido**. Señalar que se llenaron Pataz, 8 puestos, 24 h, con armas | "El cliente escribe lo que necesita como se lo diría a un proveedor, y la IA lo convierte en un pedido estructurado: lugar, puestos, horario, armamento, perfil y equipamiento." |
| 0:45 – 1:05 | **2 · Mapa de riesgo** | Señalar las 4 tarjetas, el aviso de **riesgo alto** y en el mapa: ★ Pataz, ◆ minería ilegal, burbuja naranja grande en Trujillo. Si sobra tiempo, cambiar la región a Cajamarca y volver | "Esto sirve para cualquier región del Perú. En La Libertad hay 147 denuncias por cada 10 mil habitantes, cinco conflictos sociales y cuatro estados de emergencia; Pataz, por minería ilegal. Y aquí se ve el problema: casi todas las 174 empresas autorizadas están en Trujillo, a horas del campamento. Por eso Garita recomienda vigilancia armada y sede cercana." |
| 1:05 – 1:40 | **3 · Proveedores** | Mostrar la tabla; abrir la primera empresa y su gráfico de puntaje | "En el registro de SUCAMEC hay 1,041 empresas con autorización vigente; para vigilancia con armas en La Libertad, 159, y si pido CCTV o control de accesos verificado, quedan 44. Cada una tiene un puntaje de 0 a 100 que muestra de qué se compone: autorización y vencimiento en SUCAMEC, RUC habido en SUNAT, penalidades y contratos ganados en el OECE. Cada dato tiene su fuente y su link." |
| 1:40 – 2:10 | **4 · Precio** | Mostrar la mediana y el gráfico. En "Evalúa una oferta" escribir **7000** y mostrar la alerta roja | "Este es el insight: los contratos públicos dicen '5 agentes turno mañana, 5 turno noche' en PDFs escaneados. Con OCR y un LLM los convertimos en puestos y meses: 75 contratos válidos de 19 departamentos, mediana de 9,074 soles por puesto 24/7 al mes. Y el 27 % de los contratos del Estado se paga por debajo de la planilla mínima. Una oferta de 7,000 no alcanza para pagar sueldos: alerta roja." |
| 2:10 – 2:20 | **5 · Documentos** | Clic en **Usar la versión escaneada 🧪** y señalar monto, fecha y "Vigente: vence en … días" | "El proveedor entrega su carta fianza escaneada; Garita la lee con OCR y saca el monto y el vencimiento. Es un documento sintético y la app lo marca así." |
| 2:20 – 2:30 | **6 · Solicitud de propuesta** | Clic en **Descargar en Word** | "Todo sale en una solicitud de propuesta lista para enviar a las mejores empresas, con el piso legal y los documentos que deben adjuntar." |

**Si vas atrasado:** en 2:10 salta "5 · Documentos" y ve directo a "6 · Solicitud de propuesta".

## 2:30 – 3:00 · El negocio

> "Cobramos S/ 1,500 al mes a la empresa que contrata seguridad: mineras medianas, plantas y puertos. Leer los 200 contratos nos costó 56 centavos de dólar; cada consulta de un cliente cuesta una fracción de centavo, y el servidor es gratis hoy. Después vienen una comisión de 3 a 5 % cuando intermediemos contratos y un perfil verificado para empresas de seguridad, sin vender el puntaje. Garita también funciona dentro de Claude, con un servidor MCP y una skill. Lo siguiente: validar con jefes de seguridad de mineras medianas en La Libertad."

Cortar a las 3:00 en punto. Si sobra tiempo, decir "Gracias" y esperar las preguntas.

## Plan B: si se cae el despliegue o internet

1. Decir: "Se cayó la conexión; muestro el video del software funcionando, grabado con el mismo código del repo."
2. Abrir el video de respaldo (el link está en el comentario del issue).
3. Mientras corre, narrar el mismo guion.
4. Si vuelve la conexión o hay tiempo: app en local con `uv run streamlit run app.py`.

## Si falla la API del LLM (modo demo)

- La app sigue funcionando: riesgo, proveedores, puntaje y benchmark salen de `data/processed/`. El pedido y los documentos se interpretan con reglas.
- Decir: "La API no responde ahora; la app pasa a modo demo con los datos ya procesados, que es justamente para lo que está diseñada."

## Preguntas probables

Ver [`preguntas_profesor.md`](preguntas_profesor.md): archivo, función y sección del código para cada respuesta.
