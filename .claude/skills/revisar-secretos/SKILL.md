---
name: revisar-secretos
description: Revisa que no haya claves de API, tokens ni el .env real en el repositorio de Garita ni en su historial de git. Úsala antes de cada push, antes de entregar el repo o cuando pidan revisar secretos o claves.
---

# Revisar secretos antes del push

El issue del curso lo pide explícitamente: revisar con `git log -p` que no aparezcan `api_key`, `secret` ni `token`. Esta skill lo hace con un script que **nunca imprime un valor**.

## Pasos

1. Corre el script desde la raíz del repo:

   ```bash
   uv run python .claude/skills/revisar-secretos/scripts/revisar_secretos.py
   ```

   Hace cinco revisiones: que `git check-ignore .env` responda `.env`, que ningún `.env` real esté versionado, que el historial y los archivos versionados no tengan patrones de clave, y que los valores del `.env` local no aparezcan en ningún commit.
2. Si todo sale `OK`, se puede hacer push.
3. Si algo sale `FALLA`:
   - **Archivo versionado o staged, sin commit todavía:** sácalo del índice (`git rm --cached <archivo>`), agrégalo al `.gitignore` y repite.
   - **En el historial (revisión 3 o 5):** avisa al usuario **de inmediato** que revoque la clave en platform.deepseek.com y cree otra. Borrar el archivo no basta, porque la clave sigue en los commits anteriores. No intentes reescribir el historial sin que el usuario lo pida.
   - **Falso positivo** (por ejemplo, un nombre de variable): explícalo con el archivo y la línea, sin mostrar el valor.

## Reglas

- Nunca muestres, copies ni pidas el valor de una clave. Para saber si está cargada: `uv run python -c "from garita.config import Config; print(Config.estado_credenciales())"`, que solo responde `True` o `False`.
- Nunca crees ni edites el `.env` del usuario; él lo crea en su computadora.
