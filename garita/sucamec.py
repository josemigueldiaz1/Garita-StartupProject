"""
Registro de empresas de seguridad privada autorizadas por SUCAMEC.

**Como se encontro la fuente.** Las bases de licitaciones piden verificar la
autorizacion en sucamec.gob.pe/web/index.php/empresas-de-seguridad, pero ese link
devuelve 404. La pagina oficial de gob.pe (9498-empresas-de-seguridad) enlaza al
registro vigente: una aplicacion JSF/PrimeFaces en /rgGSSP/aplicacion/resoluciones.

**Por que no basta con un GET.** La tabla llega vacia ("Se encontraron 0
Resolucion(es)"): las filas solo aparecen despues de pulsar Buscar, que dispara una
peticion AJAX de PrimeFaces. Para replicarla hay que (1) abrir la pagina y guardar la
cookie de sesion y el `javax.faces.ViewState`, (2) enviar el formulario con los mismos
nombres de campo que usa el navegador y (3) paginar la tabla con los parametros del
paginador de PrimeFaces. No se usa un navegador automatizado: tres tipos de peticion
HTTP bastan y son mas rapidas y estables.

**Con o sin armas.** El texto de la modalidad no siempre lo dice. El formulario si
tiene ese filtro, asi que las modalidades donde aplica se consultan dos veces (con
armas y sin armas) y cada fila hereda la etiqueta de la consulta que la trajo.

**El buscador corta en 2,000 resultados.** Vigilancia con armas a nivel nacional
devuelve exactamente 2,000, que es un tope y no un conteo. Por eso se consulta
departamento por departamento; si alguno vuelve a tocar el tope, el log lo advierte.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime

import pandas as pd

from .config import Config, configurar_logging, load_config
from .datos import normalizar
from .red import Cliente, decodificar

log = logging.getLogger("garita.sucamec")

# Modalidades donde el formulario distingue con y sin armas.
CON_FILTRO_ARMAS = {"1", "5", "3"}
CODIGO_ARMAS = {"CON ARMAS": "0", "SIN ARMAS": "1"}


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.1 Descarga: abre el formulario y guarda la sesion y el ViewState
class FormularioSucamec:
    """Una sesion contra el formulario JSF. Guarda cookie, ViewState y URL de accion."""

    def __init__(self, cfg: Config, cliente: Cliente | None = None):
        self.cfg = cfg
        self.url = cfg.sucamec["url"]
        self.base = re.match(r"https?://[^/]+", self.url).group(0)
        self.cli = cliente or Cliente(cfg)
        self.viewstate = ""
        self.accion = ""
        self.abrir()

    def abrir(self) -> None:
        r = self.cli.get(self.url)
        texto = decodificar(r)
        vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', texto)
        accion = re.search(r'<form id="listForm"[^>]*action="([^"]+)"', texto)
        if not vs or not accion:
            raise RuntimeError("El formulario de SUCAMEC cambio: no se encontro el ViewState.")
        self.viewstate = html.unescape(vs.group(1))
        self.accion = self.base + html.unescape(accion.group(1))

    def _campos(self, modalidad: str, armas: str, departamento: str) -> dict:
        """Los campos del formulario, con los nombres exactos que envia el navegador."""
        return {
            "listForm": "listForm",
            "listForm:j_idt16_input": modalidad,      # modalidad
            "listForm:j_idt19_input": armas,          # % | 0 con armas | 1 sin armas
            "listForm:departamento_input": departamento,
            "listForm:provincia_input": "%",
            "listForm:distrito_input": "%",
            "listForm:j_idt31_input": "0",            # tipo de busqueda por texto: ninguno
            "listForm:j_idt36": "",
            "javax.faces.ViewState": self.viewstate,
        }

    @staticmethod
    def _cabeceras() -> dict:
        return {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}

    # --- 03.2 Lectura: replica el boton Buscar y el paginador de PrimeFaces
    def buscar(self, modalidad: str, armas: str = "%", departamento: str = "%") -> tuple[int, str]:
        """Pulsa Buscar. Devuelve (total de resoluciones, html de la primera pagina)."""
        datos = self._campos(modalidad, armas, departamento) | {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "listForm:j_idt37",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "listForm:datatable",
            "listForm:j_idt37": "listForm:j_idt37",
        }
        texto = decodificar(self.cli.post(self.accion, data=datos, headers=self._cabeceras()))
        m = re.search(r"Se encontraron\s*(\d+)", texto)
        return (int(m.group(1)) if m else 0), texto

    def pagina(self, modalidad: str, armas: str, departamento: str, primero: int,
               filas: int) -> str:
        """Pide al paginador las filas [primero, primero + filas)."""
        datos = self._campos(modalidad, armas, departamento) | {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "listForm:datatable",
            "javax.faces.partial.execute": "listForm:datatable",
            "javax.faces.partial.render": "listForm:datatable",
            "listForm:datatable": "listForm:datatable",
            "listForm:datatable_pagination": "true",
            "listForm:datatable_first": str(primero),
            "listForm:datatable_rows": str(filas),
            "listForm:datatable_skipChildren": "true",
            "listForm:datatable_encodeFeature": "true",
        }
        return decodificar(self.cli.post(self.accion, data=datos, headers=self._cabeceras()))


# --- 03.2 Lectura: detecta las celdas de cada fila de la tabla
def leer_filas(texto: str) -> list[list[str]]:
    """Extrae las celdas de cada <tr data-ri=...>. El orden de columnas es el de la tabla:
    Ruc y empresa | Resolucion | Fecha vencimiento | Sede | Direccion | Ubigeo | Modalidad."""
    filas = []
    for tr in re.findall(r'<tr data-ri="\d+"[\s\S]*?</tr>', texto):
        celdas = re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)
        limpias = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in celdas]
        if len(limpias) >= 7:
            filas.append(limpias[:7])
    return filas


TOPE_BUSCADOR = 2000


def descargar_modalidad(form: FormularioSucamec, codigo: str, etiqueta: str,
                        armas: str = "%", departamento: str = "%") -> list[dict]:
    total, primera = form.buscar(codigo, armas, departamento)
    if total == 0:
        return []
    filas_pag = int(form.cfg.sucamec["filas_por_pagina"])
    filas = leer_filas(primera)
    # La primera respuesta trae 30 filas (el valor por defecto del paginador). Desde
    # ahi se piden bloques de 100 hasta completar el total que declaro el buscador.
    inicio = len(filas)
    while inicio < total:
        lote = leer_filas(form.pagina(codigo, armas, departamento, inicio, filas_pag))
        if not lote:
            log.warning("  %s: el paginador devolvio 0 filas en %d de %d", etiqueta, inicio, total)
            break
        filas.extend(lote)
        inicio += len(lote)
    etiqueta_armas = {"0": "CON ARMAS", "1": "SIN ARMAS"}.get(armas, "NO APLICA")
    if total >= TOPE_BUSCADOR:
        log.warning("  %s %s %s toco el tope de %d resultados: pueden faltar filas",
                    departamento, etiqueta, etiqueta_armas, TOPE_BUSCADOR)
    log.debug("  %-14s %-34s %-9s %5d de %5d", departamento, etiqueta, etiqueta_armas,
              len(filas), total)
    return [{"celdas": f, "modalidad": etiqueta, "armas": etiqueta_armas} for f in filas]


# --- 03.3 Limpieza: normaliza RUC, fechas, ubigeo y modalidad
def limpiar(crudas: list[dict], fecha_consulta: date) -> pd.DataFrame:
    registros = []
    for c in crudas:
        ruc_emp, resolucion, vence, sede, direccion, ubigeo, modalidad_txt = c["celdas"]
        m = re.match(r"(\d{11})\s*(.*)", ruc_emp)
        if not m:
            continue
        partes = [normalizar(p) for p in ubigeo.split("/")] + ["", "", ""]
        try:
            fv = datetime.strptime(vence.strip(), "%d/%m/%Y").date()
        except ValueError:
            fv = None
        armas = c["armas"]
        if armas == "NO APLICA" and "SIN ARMAS" in modalidad_txt.upper():
            armas = "SIN ARMAS"
        registros.append({
            "ruc": m.group(1),
            "razon_social": " ".join(m.group(2).split()),
            "resolucion": resolucion.strip(),
            "fecha_vencimiento": fv,
            "sede": normalizar(sede),
            "direccion": direccion.strip(),
            "departamento": partes[0],
            "provincia": partes[1],
            "distrito": partes[2],
            "modalidad": c["modalidad"],
            "modalidad_texto": modalidad_txt.strip(),
            "armas": armas,
        })
    df = pd.DataFrame(registros)
    antes = len(df)
    # Una misma resolucion puede salir en las consultas con y sin filtro de armas; se
    # queda la fila con la etiqueta mas especifica (CON/SIN ARMAS sobre NO APLICA).
    df["_prioridad"] = df["armas"].map({"CON ARMAS": 0, "SIN ARMAS": 1, "NO APLICA": 2})
    df = (df.sort_values("_prioridad")
            .drop_duplicates(subset=["ruc", "resolucion", "modalidad", "direccion"], keep="first")
            .drop(columns="_prioridad"))
    log.info("  limpieza: %d -> %d filas (%d duplicadas entre consultas)", antes, len(df), antes - len(df))
    df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"])
    df["fecha_consulta"] = pd.Timestamp(fecha_consulta)
    df["vigente"] = df["fecha_vencimiento"] >= df["fecha_consulta"]
    return df.reset_index(drop=True)


def resumir_empresas(res: pd.DataFrame) -> pd.DataFrame:
    """Una fila por RUC con su alcance territorial y sus modalidades vigentes."""
    v = res[res["vigente"]]
    vig = v[v["modalidad"] == "VIGILANCIA PRIVADA"]
    agg = (v.groupby("ruc")
             .agg(razon_social=("razon_social", "first"),
                  n_resoluciones=("resolucion", "nunique"),
                  n_departamentos=("departamento", "nunique"),
                  departamentos=("departamento", lambda s: "|".join(sorted(set(s)))),
                  modalidades=("modalidad", lambda s: "|".join(sorted(set(s)))),
                  vencimiento_proximo=("fecha_vencimiento", "min"))
             .reset_index())
    con_armas = set(vig.loc[vig["armas"] == "CON ARMAS", "ruc"])
    agg["vigilancia_con_armas"] = agg["ruc"].isin(con_armas)
    return agg


# --- 03.4 Salida: guarda data/processed/sucamec_resoluciones y empresas
def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    log = configurar_logging("garita.sucamec")
    log.info("SUCAMEC: descargando el registro de empresas autorizadas")
    form = FormularioSucamec(cfg)
    crudas: list[dict] = []
    for dep in cfg.sucamec["departamentos"]:
        antes = len(crudas)
        for codigo, etiqueta in cfg.sucamec["modalidades"].items():
            if codigo in CON_FILTRO_ARMAS:
                for armas in ("0", "1"):
                    crudas += descargar_modalidad(form, codigo, etiqueta, armas, dep)
            else:
                crudas += descargar_modalidad(form, codigo, etiqueta, "%", dep)
        log.info("  %-14s %5d filas", dep, len(crudas) - antes)
    hoy = date.today()
    res = limpiar(crudas, hoy)
    emp = resumir_empresas(res)
    out = cfg.processed_dir
    res.to_parquet(out / "sucamec_resoluciones.parquet", index=False)
    emp.to_parquet(out / "empresas.parquet", index=False)
    resumen = {
        "fecha_consulta": hoy.isoformat(),
        "url": cfg.sucamec["url"],
        "filas": int(len(res)),
        "vigentes": int(res["vigente"].sum()),
        "empresas_con_autorizacion_vigente": int(len(emp)),
        "empresas_vigilancia": int(emp["modalidades"].str.contains("VIGILANCIA PRIVADA").sum()),
        "peticiones": form.cli.n_peticiones,
    }
    log.info("SUCAMEC listo: %s", resumen)
    return resumen


if __name__ == "__main__":
    ejecutar()
