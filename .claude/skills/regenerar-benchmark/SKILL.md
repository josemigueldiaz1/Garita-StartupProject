---
name: regenerar-benchmark
description: Regenera el benchmark de precio por puesto-mes de Garita - descarga las Bases de los contratos de vigilancia del OECE, las lee con OCR y DeepSeek y recalcula los percentiles por departamento. Úsala cuando pidan rehacer el benchmark, sumar meses de contratos o volver a extraer puestos y turnos.
disable-model-invocation: true
argument-hint: "[opcional: --forzar para volver a extraer lo ya extraido]"
---

# Regenerar el benchmark de precios

**Gasta tokens de DeepSeek.** Cada proceso cuesta entre US$0.001 y US$0.003. El pipeline se detiene solo al llegar al tope de `GARITA_TOPE_USD` (en `.env`, por defecto US$3).

## Antes de correr

1. Confirma que la clave está cargada **sin mostrarla**:

   ```bash
   uv run python -c "from garita.config import Config; print(Config.estado_credenciales())"
   ```

   Si sale `False`, detente y pide al usuario que cree el `.env` en la raíz del repo (`notepad .env` en PowerShell, con la línea `DEEPSEEK_API_KEY=` y su clave). Nunca pidas la clave en el chat.
2. Revisa cuánto se gastó ya: `uv run python .claude/skills/regenerar-benchmark/scripts/resumen_benchmark.py --solo-costos`.

## Correr

```bash
uv run python run_pipeline.py --pasos documentos,extraer,benchmark $ARGUMENTS
```

Lo ya extraído no se vuelve a pagar: el paso `extraer` salta los procesos que ya tienen fila en `extracciones_llm.parquet`, salvo que se pase `--forzar`.

## Después

1. Resume el resultado con el script:

   ```bash
   uv run python .claude/skills/regenerar-benchmark/scripts/resumen_benchmark.py
   ```

   Muestra cuántos contratos son válidos, los percentiles por departamento, los contratos excluidos por motivo y el gasto total en dólares.
2. Revisa a mano 3 contratos al azar: que `evidencia` respalde los puestos extraídos. Si una mediana departamental se aleja mucho de la nacional con pocos casos, dilo.
3. Corre `uv run pytest -q`.
