---
name: actualizar-datos
description: Vuelve a descargar y procesar las fuentes de Garita (SUCAMEC, OECE, SUNAT, Defensoría, límites) y regenera data/processed. Úsala cuando pidan actualizar los datos, refrescar el registro de SUCAMEC o bajar meses nuevos del OECE.
disable-model-invocation: true
argument-hint: "[pasos separados por coma, ej. sucamec,proveedores]"
---

# Actualizar los datos de Garita

Corre el pipeline paso a paso y deja `data/processed` listo para la app. No gasta tokens: el paso `extraer` (LLM) queda fuera salvo que se pida. Para regenerar el precio por puesto-mes usa `/regenerar-benchmark`.

## Pasos del pipeline

| Paso | Qué hace | Fuente |
|---|---|---|
| `sucamec` | Registro de empresas autorizadas, departamento por departamento | sucamec.gob.pe |
| `oece` | Bulk mensual OCDS y filtro de contratos de vigilancia | contratacionesabiertas.oece.gob.pe |
| `documentos` | Descarga de Bases, triaje texto/imagen y OCR de las páginas escaneadas | SEACE |
| `extraer` | DeepSeek lee los términos de referencia (gasta tokens) | API de DeepSeek |
| `benchmark` | Precio por puesto-mes y percentiles por departamento | — |
| `proveedores` | Ficha del buscador de proveedores del OECE por RUC | eap.oece.gob.pe |
| `sunat` | Padrón reducido del RUC (395 MB) | sunat.gob.pe |
| `defensoria` | Último reporte de conflictos sociales | defensoria.gob.pe |
| `geo` | Provincias disueltas desde los distritos de la sesión 06 | repo del curso |
| `confianza` | Componentes fijos del puntaje de confianza | — |
| `metadatos` | Fechas de corte y conteos | — |

## Cómo correrlo

1. Si `$ARGUMENTS` trae pasos, usa esos. Si viene vacío, corre todos menos `extraer`:

   ```bash
   uv run python run_pipeline.py --pasos sucamec,oece,documentos,benchmark,proveedores,sunat,defensoria,geo,confianza,metadatos
   ```

   Con argumentos: `uv run python run_pipeline.py --pasos $ARGUMENTS`.

2. Corre en segundo plano: SUCAMEC y la ficha del OECE consultan de a una por segundo y el padrón de SUNAT pesa 395 MB. No lo interrumpas a la mitad; cada paso escribe su tabla al terminar.
3. Si un paso falla, lee `logs/` y aplica depuración sistemática antes de reintentar. Una fuente caída no rompe la app: sigue con la última versión de su tabla.
4. Al terminar, corre `/preparar-demo` para confirmar que ninguna tabla quedó vacía.
5. Resume qué cambió: filas antes y después de cada tabla, y la fecha nueva de `data/processed/metadatos.json`.

No hagas commit sin que el usuario lo pida; antes de cualquier push, `/revisar-secretos`.
