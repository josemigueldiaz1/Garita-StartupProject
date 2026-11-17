# data/manual

Tablas **curadas a mano** a partir de fuentes oficiales. No las genera el pipeline: se actualizan revisando las normas publicadas y se versionan en el repo.

## `estados_emergencia.csv`

Estados de emergencia por criminalidad, minería ilegal, narcotráfico y control fronterizo en el Perú. Es la segunda señal de riesgo por zona de Garita. Complementa los conflictos sociales de la Defensoría del Pueblo, que no registran la criminalidad: por ejemplo, la Defensoría tiene pocos casos en La Libertad, pero Pataz está en emergencia por la minería ilegal.

**Fecha de corte: 16 de noviembre de 2026.**

**Fuente:** el texto oficial de cada decreto supremo en el [buscador de normas legales del Diario Oficial El Peruano](https://busquedas.elperuano.pe/). Cada fila enlaza su norma. La única excepción es el DS 056-2026-PCM: su enlace es una copia de la página de Normas Legales de El Peruano del 16 de abril de 2026, publicada por un medio, porque no se ubicó su ficha en el buscador.

### Columnas

| Columna | Descripción |
|---|---|
| `departamento`, `provincia` | En mayúsculas y sin tildes, como en los límites de la sesión 06. Lima Metropolitana es `LIMA, LIMA` y el Callao es `CALLAO, CALLAO` |
| `distrito` | Vacío si el decreto cubre **toda la provincia**. Si cubre solo algunos distritos, van separados por `\|` |
| `norma` | Decreto supremo vigente (la última prórroga encontrada) |
| `fecha_inicio`, `fecha_fin` | Plazo de la última prórroga encontrada, en formato AAAA-MM-DD |
| `motivo` | Resumen del artículo 1 del decreto. Si dice **"Verificar vigencia"**, no se encontró una prórroga posterior y la fila no debe mostrarse como vigente sin revisarla |
| `url` | Enlace a la norma |

Hay una fila por provincia y por decreto. Si una provincia está en dos decretos distintos (por ejemplo, Satipo y La Convención, por el VRAEM y por el DS 146-2026-PCM), aparece dos veces.

### Cómo se calcularon las fechas

- Los estados de emergencia duran como máximo 60 días calendario. `fecha_fin` es `fecha_inicio + 59 días`: el día de inicio cuenta como el primero.
- Cuando el decreto no dice desde cuándo rige, se toma el día siguiente a su publicación, que es la regla general (art. 109 de la Constitución). Con ese criterio, el DS 132-2026-PCM de Pisco vence el 18 de noviembre de 2026, la misma fecha que informa el Congreso.
- Una zona está vigente si `fecha_fin` es mayor o igual a la fecha de consulta. Al corte, 31 de las 49 filas están vigentes.

### Qué no incluye

- **Corredor Vial Sur Apurímac-Cusco-Arequipa:** no se encontró un decreto de 2026; el último ubicado es de 2025.
- **Emergencias por lluvias, El Niño o sismos:** no son una señal de riesgo de seguridad.
- **El DS 148-2026-PCM** (penales de alta peligrosidad): no corresponde a una zona geográfica.
- **Los centros poblados y las franjas territoriales del VRAEM** (Eje Energético del Gas de Camisea y Corredor Fluvial-Terrestre del Ene) no tienen fila propia: se mencionan en el `motivo`.

### Cómo actualizarla

1. En el [buscador de El Peruano](https://busquedas.elperuano.pe/), buscar "prorroga el Estado de Emergencia" y "declara el Estado de Emergencia" en las normas de la PCM publicadas desde la fecha de corte.
2. Por cada decreto nuevo, leer el artículo 1: zonas, fecha de inicio y plazo. Desde 2026, cada prórroga requiere la aprobación del Senado.
3. Reemplazar las filas de esa zona con la nueva norma y sus fechas; agregar filas para las zonas nuevas.
4. Revisar las filas que dicen "Verificar vigencia" y las que vencen antes de la siguiente actualización.
5. Cambiar la fecha de corte de este archivo.

Conviene revisarla cada dos semanas, porque las prórrogas se publican pocos días antes de que venza cada plazo de 60 días.
