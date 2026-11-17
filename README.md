# Garita

**Ayudamos a mineras y empresas a contratar seguridad privada confiable en el Perú: verificamos proveedores contra SUCAMEC, OECE y SUNAT, comparamos precios con contratos públicos reales y recomendamos según el riesgo de la zona.**

> Proyecto final del curso Data Science con Python, Universidad del Pacífico (2026-II). En construcción: este README se completa con las 9 partes antes de la presentación del miércoles 18 de noviembre.

## Qué hace

1. El cliente describe su necesidad: lugar, puestos, horario, perfil del personal, armamento y equipamiento.
2. Garita muestra el riesgo de la zona por provincia con los conflictos registrados por la Defensoría del Pueblo.
3. Devuelve una lista corta de empresas con autorización vigente de SUCAMEC para esa modalidad y departamento, con un puntaje de confianza de 0 a 100 que muestra de qué se compone.
4. Compara el precio con un benchmark de soles por puesto-mes construido con contratos públicos del OECE, y alerta si una oferta queda por debajo del costo laboral mínimo.
5. Lee cartas fianza y pólizas para sacar montos y fechas de vencimiento, y exporta la solicitud de propuesta.

## Fuentes

| Fuente | Qué aporta |
|---|---|
| [SUCAMEC, empresas de seguridad autorizadas](https://www.sucamec.gob.pe/rgGSSP/aplicacion/resoluciones/List.xhtml) | Autorización por modalidad, sede y fecha de vencimiento |
| [OECE, contrataciones abiertas (OCDS)](https://contratacionesabiertas.oece.gob.pe) | Contratos públicos de vigilancia, montos, plazos y Bases |
| [OECE, buscador de proveedores](https://apps.osce.gob.pe/perfilprov-ui/) | Inhabilitaciones, penalidades y sanciones |
| [SUNAT, padrón reducido del RUC](https://www.sunat.gob.pe/descargaPRR/padron_reducido_ruc.zip) | Estado y condición del contribuyente |
| [Defensoría del Pueblo, reportes de conflictos sociales](https://www.defensoria.gob.pe/categorias_de_documentos/reportes/) | Conflictos por provincia |
