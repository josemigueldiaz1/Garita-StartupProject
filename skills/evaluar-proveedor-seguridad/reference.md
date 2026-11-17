# Referencia: evaluar proveedor de seguridad

Se lee solo cuando hace falta. El método está en `SKILL.md`.

## Modalidades SUCAMEC

El registro de SUCAMEC autoriza a cada empresa por **modalidad** y por **sede**. Una empresa puede estar autorizada para vigilancia en Lima y no en La Libertad. Estas son las modalidades que Garita descarga, con la etiqueta que usan las herramientas:

| Etiqueta en Garita | Qué cubre | Cuándo pedirla |
|---|---|---|
| `VIGILANCIA PRIVADA` | Vigilantes en puestos fijos. El registro distingue **con armas** y **sin armas** | Mina, campamento, planta, almacén u oficina |
| `PROTECCION PERSONAL` | Resguardo de personas | Ejecutivos y visitas |
| `TRANSPORTE DE DINERO Y VALORES` | Traslado de efectivo y valores | Pago de planillas, recaudación |
| `TECNOLOGIA - VIDEO A DISTANCIA` | Monitoreo de cámaras (CCTV) | Si el pedido incluye cámaras con monitoreo |
| `TECNOLOGIA - GPS` | Rastreo satelital | Flota, convoyes de concentrado |
| `TECNOLOGIA - CONTROL DE ACCESOS` | Sistemas de acceso | Garitas, campamentos |
| `TECNOLOGIA - CENTRALES RECEPTORAS` | Centrales de alarma | Instalaciones con alarmas |
| `TECNOLOGIA - SEGURIDAD` | Otros servicios de tecnología | |
| `CONSULTORIA Y ASESORIA` | Estudios de seguridad | Análisis de riesgo previo |

El equipamiento que no es una modalidad SUCAMEC (vehículos, radios, uniformes, tipo de arma) **no se puede verificar**: va en la solicitud de propuesta y la empresa lo declara.

## Puesto 24/7 equivalente

Los contratos mezclan jornadas. Para comparar precios, Garita convierte todo a **puestos 24/7 equivalentes** por horas:

- Un puesto de 24 horas = 1
- Un puesto de 12 horas = 0.5
- Un puesto de *h* horas = *h* / 24

**Precio por puesto-mes** = monto del contrato / (puestos 24/7 equivalentes × meses).

## Piso legal de un puesto

Es lo mínimo que cuesta cubrir un puesto con planilla formal (`garita/benchmark.py`, supuestos en `config.yaml → costo_laboral`):

1. **Agentes necesarios** = horas del puesto al mes / horas efectivas de un agente (48 h por semana, descontando el mes de vacaciones). Un puesto 24/7 necesita unos 3.8 agentes.
2. **Costo por agente** = remuneración mínima vital (con recargo nocturno del 35 % para las horas entre 10 p. m. y 6 a. m.) + EsSalud + SCTR + vida ley + gratificaciones con su bonificación + CTS + vacaciones.
3. **Piso** = costo por agente × agentes + un margen mínimo del 10 % para la empresa.

Una oferta por debajo del piso solo cierra si la empresa no paga la planilla completa. Es una **señal de informalidad**, no una prueba.

## Niveles de dato

| Nivel | Qué significa | Ejemplos |
|---|---|---|
| `verificado` | Fuente oficial, con link | Autorización SUCAMEC, condición SUNAT, apto para contratar y penalidades del OECE, monto de un contrato |
| `extraido` | Garita lo leyó de un documento oficial con OCR o un LLM; puede tener errores de lectura | Puestos, turnos y armamento de las Bases; conflictos por provincia del PDF de la Defensoría |
| `declarado` | Lo dice la empresa o el cliente | Precio ofertado, tipo de arma, vehículos, carta fianza subida por el proveedor |
| `sintetico` | Inventado para el demo, etiquetado | Documentos de `data/demo/` |

## Señales de alerta

- Autorización SUCAMEC vencida o que vence en menos de 90 días.
- RUC con estado distinto de `ACTIVO` o condición `NO HABIDO` en SUNAT.
- No apta para contratar con el Estado, o con penalidades o sanciones en el OECE.
- Oferta bajo el piso legal (🔴) o bajo el percentil 25 del mercado (🟠).
- Sin sede autorizada en el departamento del servicio.

## Lo que Garita no tiene (integración futura)

Deuda coactiva en SUNAT, centrales de riesgo privadas (Equifax, Sentinel) y sanciones de SUNAFIL o SUCAMEC no tienen descarga pública masiva. Si el usuario las pide, dilo y sugiere pedirlas como documento al proveedor.

## Fuentes

| Fuente | URL |
|---|---|
| SUCAMEC, empresas de seguridad autorizadas | https://www.sucamec.gob.pe/rgGSSP/aplicacion/resoluciones/List.xhtml |
| SUCAMEC en gob.pe | https://www.gob.pe/institucion/sucamec/pages/9498-empresas-de-seguridad |
| OECE, contrataciones abiertas (OCDS) | https://contratacionesabiertas.oece.gob.pe/api/v1 |
| OECE, un proceso por su ocid | https://contratacionesabiertas.oece.gob.pe/api/v1/record/{ocid} |
| OECE, buscador de proveedores del Estado | https://apps.osce.gob.pe/perfilprov-ui/ficha/{ruc} |
| SUNAT, padrón reducido del RUC | https://www.sunat.gob.pe/descargaPRR/padron_reducido_ruc.zip |
| Defensoría del Pueblo, reportes de conflictos sociales | https://www.defensoria.gob.pe/categorias_de_documentos/reportes/ |
| Remuneración mínima vital | https://www.gob.pe/institucion/mtpe/normas-legales/6328574-006-2024-tr |
