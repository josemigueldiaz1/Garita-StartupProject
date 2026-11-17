# Diccionario de datos

Todo lo que lee la app vive en `data/processed/` y se versiona en el repo: es el **modo demo**. Si falta la clave del LLM o se cae una fuente, la app funciona igual con estas tablas. El pipeline (`run_pipeline.py`) las regenera.

Cada dato que se muestra en la app lleva su **nivel**:

| Nivel | Qué significa | Ejemplo |
|---|---|---|
| `verificado` | Viene de una fuente oficial, con link | Autorización SUCAMEC, condición SUNAT, penalidades OECE |
| `extraido` | Lo sacó Garita de un documento oficial con OCR o LLM; puede tener errores de lectura | Puestos y turnos leídos de las Bases de un contrato |
| `declarado` | Lo dice la empresa o el cliente, sin verificación | Tipo de arma, vehículos, carta fianza subida por el proveedor |
| `sintetico` | Inventado para el demo, etiquetado como tal | La carta fianza de ejemplo de `data/demo/` |

## Tablas

### `sucamec_resoluciones.parquet` · una fila por resolución y sede
| Columna | Tipo | Descripción |
|---|---|---|
| `ruc` | str (11) | RUC de la empresa |
| `razon_social` | str | |
| `resolucion` | str | Número de resolución de autorización |
| `fecha_vencimiento` | date | Vencimiento de la autorización |
| `vigente` | bool | `fecha_vencimiento >= fecha_consulta` |
| `sede` | str | `PRINCIPAL` o el tipo de sede que publica SUCAMEC |
| `direccion` | str | Dirección de la sede (de la empresa, no de personas) |
| `departamento`, `provincia`, `distrito` | str | Ubigeo de la sede, en mayúsculas y sin tildes |
| `modalidad` | str | Etiqueta corta de `config.yaml → sucamec.modalidades` (ej. `VIGILANCIA PRIVADA`) |
| `modalidad_texto` | str | Texto original de SUCAMEC |
| `armas` | str | `CON ARMAS`, `SIN ARMAS` o `NO APLICA` |
| `fecha_consulta` | date | Día de la descarga |

### `empresas.parquet` · una fila por RUC
`ruc`, `razon_social`, `n_resoluciones`, `n_departamentos`, `departamentos` (separados por `|`), `modalidades` (separadas por `|`), `vigilancia_con_armas` (bool), `vencimiento_proximo` (date, la autorización vigente que vence antes).

### `contratos_vigilancia.parquet` · una fila por proceso del OECE (ocid)
`ocid`, `titulo`, `descripcion`, `entidad`, `departamento`, `monto_contrato` (S/), `fecha_firma`, `fecha_inicio`, `fecha_fin`, `duracion_dias`, `ruc_proveedor`, `proveedor`, `es_consorcio` (bool), `url_bases`, `url_contrato`, `mes_archivo`.

### `extracciones_llm.parquet` · una fila por proceso con Bases leídas
`ocid`, `n_puestos`, `n_puestos_24h`, `n_puestos_12h`, `n_puestos_otros`, `n_agentes`, `meses`, `armado` (`si`, `no`, `mixto`, `no_indica`), `incluye_supervisor`, `estatura_min_m`, `edad_max`, `experiencia_min_meses`, `tipo_arma`, `equipamiento`, `confianza` (`alta`, `media`, `baja`), `evidencia` (cita textual corta), `paginas`, `tokens_entrada`, `tokens_salida`, `costo_usd`, `error`.

### `benchmark_contratos.parquet` · contratos con precio normalizado
Las columnas de `contratos_vigilancia` más las de la extracción y:
`puestos_equivalentes_24h` (un puesto de 12 h cuenta 0.5), `precio_puesto_mes` (S/ por puesto 24/7 equivalente y mes), `valido` (bool) y `motivo_exclusion`.

### `benchmark_departamento.parquet` · el benchmark
`departamento` (o `PERU` para el total), `n`, `p25`, `mediana`, `p75`, `minimo`, `maximo`.

### `proveedores_oece.parquet` · ficha del buscador de proveedores del OECE
`ruc`, `apto_contratar` (bool), `habilitado` (bool), `n_penalidades` (int), `n_sanciones` (int), `actualizado_al` (date), `url_ficha`.

### `experiencia_publica.parquet` · contratos públicos de vigilancia ganados
`ruc`, `n_contratos`, `monto_total`, `ultimo_contrato` (date), `departamentos` (separados por `|`).

### `sunat_ruc.parquet` · padrón reducido del RUC
`ruc`, `estado` (ej. `ACTIVO`), `condicion` (ej. `HABIDO`), `ubigeo`, `fecha_padron`.

### `conflictos.parquet` · una fila por caso del reporte de la Defensoría
`reporte`, `mes`, `caso`, `tipo`, `estado`, `departamento`, `provincia`, `distrito`, `pagina`.

### `conflictos_provincia.parquet` y `provincias.geojson`
`departamento`, `provincia`, `n_casos`, `n_socioambientales`, `n_activos`. El GeoJSON tiene las mismas llaves y la geometría disuelta desde los distritos de la sesión 06.

### `metadatos.json`
Fecha de corte y conteos de cada fuente. La app los muestra al pie de cada sección.
