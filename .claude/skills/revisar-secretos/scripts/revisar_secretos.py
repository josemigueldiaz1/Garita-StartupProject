"""
revisar_secretos.py — ninguna clave en el repo ni en su historial, antes de cada push.

    uv run python .claude/skills/revisar-secretos/scripts/revisar_secretos.py

Hace cinco revisiones e imprime OK o FALLA en cada una. **Nunca imprime un valor**:
de un hallazgo solo dice donde esta, que patron cumplio y cuantos caracteres tiene.

1. `git check-ignore .env` responde `.env`.
2. Ningun .env real esta versionado (solo .env.example).
3. El historial completo (`git log -p --all`) no contiene patrones de clave.
4. Los archivos versionados hoy tampoco.
5. Si existe el .env local, sus valores no aparecen en ningun commit. Es la prueba mas
   fuerte: no depende de adivinar el formato de la clave.

Si la revision 3 o la 5 fallan, borrar el archivo NO basta: la clave quedo en el
historial y hay que revocarla en platform.deepseek.com y crear otra.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ===== HERRAMIENTA 16 · Skills de Claude Code =====
# --- 16.1 Arranque: encontrar git aunque no este en el PATH
def encontrar_git() -> str:
    """git del PATH; si no hay, el de Git for Windows o el que trae GitHub Desktop."""
    en_path = shutil.which("git")
    if en_path:
        return en_path
    candidatos = [r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files (x86)\Git\cmd\git.exe"]
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        # GitHub Desktop cambia de carpeta en cada version (app-3.6.11, app-3.6.12...): se
        # toma la mas reciente en vez de fijar una.
        candidatos += sorted(glob.glob(os.path.join(local, "GitHubDesktop", "app-*", "resources",
                                                    "app", "git", "cmd", "git.exe")), reverse=True)
    for c in candidatos:
        if os.path.exists(c):
            return c
    sys.exit("FALLA  no encontre git. Instala Git o agregalo al PATH.")


GIT = encontrar_git()


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def raiz_repo() -> Path:
    r = git("rev-parse", "--show-toplevel")
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return Path(__file__).resolve().parents[4]


# --- 16.5 Patrones: formas tipicas de una clave escrita en un archivo
PATRONES = {
    "clave tipo sk-": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "asignacion de clave": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.\/+]{12,})"),
    "token de GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "token de Hugging Face": re.compile(r"hf_[A-Za-z0-9]{30,}"),
}
# Valores que no son claves: lecturas de variables de entorno, nombres de variables o
# llamadas a funciones (`api_key=Config.credencial("DEEPSEEK_API_KEY")`).
NO_ES_CLAVE = re.compile(r"(?i)getenv|environ|credencial|secrets|config\.|settings\.|^[A-Z_]+$|tu[_-]?clave|xxxx|\.\.\.")


def buscar(texto: str) -> list[tuple[str, int]]:
    """Hallazgos en un texto: (patron, largo del valor). El valor no sale de aqui."""
    hallazgos = []
    for nombre, patron in PATRONES.items():
        for m in patron.finditer(texto):
            valor = m.group(m.lastindex) if m.lastindex else m.group(0)
            despues = texto[m.end():m.end() + 1]
            if despues == "(" or NO_ES_CLAVE.search(valor):
                continue
            hallazgos.append((nombre, len(valor)))
    return hallazgos


def valores_env(raiz: Path) -> dict[str, str]:
    """Valores del .env local para buscarlos en el historial. Se usan, no se imprimen."""
    ruta = raiz / ".env"
    if not ruta.exists():
        return {}
    valores = {}
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            v = v.strip().strip("\"'")
            if len(v) >= 12:   # topes como GARITA_TOPE_USD=3.00 no son secretos
                valores[k.strip()] = v
    return valores


# --- 16.6 Revisiones: cada una imprime OK o FALLA, nunca el valor encontrado
def main() -> int:
    raiz = raiz_repo()
    fallas = 0

    def reporte(ok: bool, texto: str) -> None:
        nonlocal fallas
        fallas += 0 if ok else 1
        print(("OK     " if ok else "FALLA  ") + texto)

    r = git("check-ignore", ".env", cwd=raiz)
    reporte(r.stdout.strip() == ".env", "git check-ignore .env responde .env")

    versionados = git("ls-files", cwd=raiz).stdout.splitlines()
    env_versionados = [f for f in versionados if re.search(r"(^|/)\.env(\..+)?$", f) and not f.endswith(".env.example")]
    reporte(not env_versionados, ".env no esta versionado" if not env_versionados
            else f".env versionado: {', '.join(env_versionados)}")

    historial = git("log", "-p", "--all", "--no-color", cwd=raiz).stdout
    en_historial = buscar(historial)
    reporte(not en_historial, "historial sin patrones de clave" if not en_historial else
            "historial con " + "; ".join(f"{n} ({largo} caracteres, valor enmascarado)" for n, largo in en_historial[:5]))

    en_archivos = []
    for f in versionados:
        ruta = raiz / f
        if not ruta.is_file() or ruta.stat().st_size > 2_000_000 or ruta.suffix in {".parquet", ".png", ".jpg", ".pdf", ".zip"}:
            continue
        try:
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        en_archivos += [(f, n, largo) for n, largo in buscar(texto)]
    reporte(not en_archivos, "archivos versionados sin patrones de clave" if not en_archivos else
            "posibles claves en " + "; ".join(f"{f} ({n}, {largo} caracteres)" for f, n, largo in en_archivos[:5]))

    valores = valores_env(raiz)
    if valores:
        filtrados = [k for k, v in valores.items() if v in historial]
        reporte(not filtrados, "los valores del .env local no aparecen en ningun commit" if not filtrados
                else f"el valor de {', '.join(filtrados)} aparece en el historial: REVOCA la clave ya")
    else:
        print("INFO   no hay .env local con valores: se omite la revision 5")

    print("\nResultado:", "sin secretos, se puede hacer push" if fallas == 0
          else f"{fallas} falla(s): no hagas push hasta resolverlas")
    return 1 if fallas else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
