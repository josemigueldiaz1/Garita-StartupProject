"""
Contratos publicos de vigilancia del OECE (estandar OCDS) y ficha de cada proveedor.

Reutiliza la adquisicion del HW3 (tarea2_radar/src/adquisicion.py): la API
`contratacionesabiertas.oece.gob.pe/api/v1/files` lista los archivos mensuales, y cada
mes es un ZIP de 22 CSV con los compiled releases (una foto por proceso, el ocid).

**Que se agrega respecto al HW3.** Alli bastaban tres tablas. Para el benchmark de
precios hacen falta siete: articulos (para filtrar por la clasificacion del catalogo,
no por palabras sueltas del titulo), contratos (monto firmado y plazo en dias),
proveedores adjudicados (RUC del ganador), partes (departamento de la entidad) y los
documentos de la licitacion y del contrato (links a las Bases y al contrato firmado).

**Por que filtrar por clasificacion y no por titulo.** Buscar "vigilancia" en el titulo
trae camaras de videovigilancia, uniformes de serenazgo y obras de "centrales de
vigilancia". La clasificacion CUBSO del item "SERVICIO DE SEGURIDAD Y VIGILANCIA" es la
que pone la propia entidad al convocar; el titulo solo se usa como respaldo, con una
lista de exclusiones.
"""

from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path

import pandas as pd

from .config import Config, configurar_logging, load_config
from .datos import normalizar
from .red import Cliente

log = logging.getLogger("garita.oece")


def _col(df: pd.DataFrame, *fragmentos: str) -> str:
    """La primera columna cuyo nombre contiene todos los fragmentos (sin tildes)."""
    for c in df.columns:
        nc = normalizar(c)
        if all(normalizar(f) in nc for f in fragmentos):
            return c
    raise KeyError(f"No hay columna con {fragmentos}")


def _leer(zf: zipfile.ZipFile, nombre: str) -> pd.DataFrame:
    with zf.open(nombre) as fh:
        return pd.read_csv(fh, low_memory=False, dtype=str)


# ===== HERRAMIENTA 03 · Scraping y APIs =====
# --- 03.5 Descarga: catalogo de meses y ZIP mensual de la API OCDS del OECE
def descargar_meses(cfg: Config, cli: Cliente) -> list[Path]:
    o = cfg.oece
    d = cli.get(f"{o['api_base']}/files", params={"page": 1, "paginateBy": 60},
                headers={"Accept": "application/json"}).json()
    catalogo = {(r["year"], r["month"]): r["files"] for r in d.get("results", [])
                if r.get("source") == o["fuente"]}
    rutas = []
    for m in o["meses"]:
        clave = (str(m["anio"]), m["mes"])
        if clave not in catalogo:
            raise RuntimeError(f"El mes {clave} no esta en el catalogo del OECE.")
        destino = cfg.raw_dir / "oece" / f"{clave[0]}-{clave[1]}_{o['formato']}.zip"
        existia = destino.exists()
        cli.descargar(catalogo[clave][o["formato"]], destino)
        log.info("  %s-%s %s (%.1f MB)", *clave, "en cache" if existia else "descargado",
                 destino.stat().st_size / 1e6)
        rutas.append(destino)
    return rutas


# --- 03.6 Lectura: une las siete tablas del ZIP en una fila por proceso de vigilancia
def procesos_de_vigilancia(zip_path: Path, cfg: Config) -> pd.DataFrame:
    o = cfg.oece
    with zipfile.ZipFile(zip_path) as zf:
        reg = _leer(zf, "Registros.csv")
        art = _leer(zf, "Ent_Lic_ArticulosQueSeAdquirira.csv")
        par = _leer(zf, "Ent_PartesInvolucradas.csv")
        con = _leer(zf, "Ent_Contratos.csv")
        prov = _leer(zf, "Ent_Adj_Proveedores.csv")
        ldoc = _leer(zf, "Ent_Lic_Documentos.csv")
        cdoc = _leer(zf, "Ent_Con_Documentos.csv")

    OCID = "Open Contracting ID"
    # Filtro 1: clasificacion del item
    c_clas = _col(art, "Articulos que se adquiriran:Clasificacion:Descripcion")
    por_item = set(art.loc[art[c_clas].fillna("").str.upper()
                           .str.contains(o["clasificacion_vigilancia"], regex=False), OCID])
    # Filtro 2 (respaldo): titulo, con exclusiones
    c_tit = _col(reg, "Licitacion:Titulo de la licitacion")
    c_des = _col(reg, "Licitacion:Descripcion de la licitacion")
    texto = (reg[c_tit].fillna("") + " " + reg[c_des].fillna("")).str.lower()
    por_titulo = set(reg.loc[texto.str.contains(o["patron_titulo"], regex=True)
                             & ~texto.str.contains(o["patron_exclusion"], regex=True), OCID])
    ocids = por_item | por_titulo
    r = reg[reg[OCID].isin(ocids)].copy()
    if r.empty:
        return pd.DataFrame()

    n_items = art[art[OCID].isin(ocids)].groupby(OCID).size()

    # Contratos: monto firmado, plazo y adjudicacion
    c_cid = _col(con, "Contratos:ID del Contrato")
    c_adj = _col(con, "Contratos:ID de Adjudicacion")
    c_monto = _col(con, "Contratos:Valor:Monto")
    c_ini = _col(con, "Contratos:Periodo:Fecha de inicio")
    c_fin = _col(con, "Contratos:Periodo:Fecha de fin")
    c_dur = _col(con, "Contratos:Periodo:Duracion")
    c_firma = _col(con, "Contratos:Fecha de firma")
    cc = con[con[OCID].isin(ocids)].copy()
    cc[c_monto] = pd.to_numeric(cc[c_monto], errors="coerce")
    cc[c_dur] = pd.to_numeric(cc[c_dur], errors="coerce")

    # Proveedor ganador de cada adjudicacion
    p_adj = _col(prov, "Adjudicaciones:ID de Adjudicacion")
    p_id = _col(prov, "Proveedores:ID de Organizacion")
    p_nom = _col(prov, "Proveedores:Nombre de la Organizacion")
    pv = prov[prov[OCID].isin(ocids)][[p_adj, p_id, p_nom]].drop_duplicates(p_adj)
    cc = cc.merge(pv, left_on=c_adj, right_on=p_adj, how="left")

    agg = (cc.groupby(OCID)
             .agg(n_contratos=(c_cid, "nunique"),
                  monto_contrato=(c_monto, "sum"),
                  duracion_dias=(c_dur, "max"),
                  fecha_inicio=(c_ini, "min"),
                  fecha_fin=(c_fin, "max"),
                  fecha_firma=(c_firma, "min"),
                  id_proveedor=(p_id, "first"),
                  proveedor=(p_nom, "first"),
                  n_proveedores=(p_id, "nunique"),
                  id_contrato=(c_cid, "first"))
             .reset_index())

    # Departamento de la entidad compradora (rol buyer, como en el HW3)
    c_rol = _col(par, "Partes involucradas:Roles de las partes")
    c_dep = _col(par, "Partes involucradas:Direccion:Departamento")
    comp = par[par[OCID].isin(ocids) & par[c_rol].fillna("").str.contains("buyer", case=False)]
    comp = comp.drop_duplicates(OCID)[[OCID, c_dep]]

    # Bases: se prefieren las integradas (version final, con consultas absueltas)
    d_url = _col(ldoc, "Licitacion:Documentos:URL")
    d_tit = _col(ldoc, "Licitacion:Documentos:Titulo")
    d_tipo = _col(ldoc, "Licitacion:Documentos:Tipo de Documento")
    lb = ldoc[ldoc[OCID].isin(ocids) & (ldoc[d_tipo] == "biddingDocuments")].copy()
    lb["_prio"] = lb[d_tit].fillna("").str.contains("ntegrad", case=False).map({True: 0, False: 1})
    bases = lb.sort_values("_prio").drop_duplicates(OCID)[[OCID, d_url, d_tit]]

    e_url = _col(cdoc, "Contratos:Documentos:URL")
    e_tipo = _col(cdoc, "Contratos:Documentos:Tipo de Documento")
    contrato_pdf = (cdoc[cdoc[OCID].isin(ocids) & (cdoc[e_tipo] == "contractSigned")]
                    .drop_duplicates(OCID)[[OCID, e_url]])

    # En SEACE el "titulo" OCDS es la nomenclatura del proceso (CP SER-SM-1-2026-...);
    # el texto que describe el servicio esta en la descripcion.
    out = r[[OCID, c_tit, c_des, _col(reg, "Comprador:Nombre de la Organizacion"),
             _col(reg, "Licitacion:Valor:Monto"),
             _col(reg, "Licitacion:Detalles del metodo de contratacion")]].copy()
    out.columns = ["ocid", "nomenclatura", "descripcion", "entidad", "valor_estimado", "metodo"]
    out = (out.merge(agg.rename(columns={OCID: "ocid"}), on="ocid", how="left")
              .merge(comp.rename(columns={OCID: "ocid", c_dep: "departamento"}), on="ocid", how="left")
              .merge(bases.rename(columns={OCID: "ocid", d_url: "url_bases", d_tit: "titulo_bases"}),
                     on="ocid", how="left")
              .merge(contrato_pdf.rename(columns={OCID: "ocid", e_url: "url_contrato"}),
                     on="ocid", how="left"))
    out["n_items"] = out["ocid"].map(n_items).fillna(0).astype(int)
    out["por_clasificacion"] = out["ocid"].isin(por_item)
    out["mes_archivo"] = zip_path.name[:7]
    return out


# --- 03.7 Limpieza: RUC del ganador, departamento canonico y montos
def limpiar_contratos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("mes_archivo").drop_duplicates("ocid", keep="last").copy()
    df["departamento"] = df["departamento"].map(normalizar).replace({
        "LIMA METROPOLITANA": "LIMA", "PROV. CONST. DEL CALLAO": "CALLAO",
        "PROVINCIA CONSTITUCIONAL DEL CALLAO": "CALLAO"})
    ident = df["id_proveedor"].fillna("").str.replace("PE-RUC-", "", regex=False)
    df["ruc_proveedor"] = ident.where(ident.str.fullmatch(r"\d{11}"), None)
    # Un consorcio no tiene RUC de 11 digitos en OCDS: queda marcado, no se descarta,
    # pero no suma experiencia a ninguna empresa individual.
    df["es_consorcio"] = df["proveedor"].fillna("").str.upper().str.startswith("CONSORCIO") | (
        df["ruc_proveedor"].isna() & df["id_proveedor"].notna())
    for c in ("monto_contrato", "valor_estimado", "duracion_dias"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("fecha_inicio", "fecha_fin", "fecha_firma"):
        df[c] = pd.to_datetime(df[c], errors="coerce", utc=True).dt.tz_localize(None)
    df["con_contrato"] = df["monto_contrato"].fillna(0) > 0
    return df.reset_index(drop=True)


def experiencia_publica(contratos: pd.DataFrame) -> pd.DataFrame:
    c = contratos[contratos["con_contrato"] & contratos["ruc_proveedor"].notna()]
    return (c.groupby("ruc_proveedor")
              .agg(n_contratos=("ocid", "nunique"),
                   monto_total=("monto_contrato", "sum"),
                   ultimo_contrato=("fecha_firma", "max"),
                   departamentos=("departamento", lambda s: "|".join(sorted(set(s.dropna())))))
              .reset_index()
              .rename(columns={"ruc_proveedor": "ruc"}))


# --- 03.8 Descarga: ficha publica del proveedor (inhabilitacion, penalidades, sanciones)
def ficha_proveedor(cli: Cliente, cfg: Config, ruc: str) -> dict:
    """
    Consulta la ficha del Buscador de Proveedores del Estado para un RUC.

    `esAptoContratar` es falso cuando el proveedor esta inhabilitado o suspendido por
    el Tribunal de Contrataciones; `seccionPenalidadF01` trae el numero de penalidades
    aplicadas en contratos. Solo se guardan esas banderas: la ficha tambien trae correos
    y telefonos, que Garita no necesita y no almacena.
    """
    d = cli.get(cfg.oece["ficha_proveedor"].format(ruc=ruc),
                headers={"Accept": "application/json"}).json()
    p = d.get("proveedorT01") or {}
    est = d.get("estadisticaT01") or {}
    pen = ((est.get("seccionPenalidadF01") or {}).get("datosEstadisticaT01") or {}).get("valor")
    san = (est.get("seccionSancionF01") or {})
    n_san = len(san.get("sancionesT01") or [])
    san_dato = (san.get("datosEstadisticaT01") or {}).get("valor")
    return {
        "ruc": ruc,
        "en_registro": bool(p),
        "apto_contratar": p.get("esAptoContratar"),
        "habilitado": p.get("esHabilitado"),
        "n_penalidades": int(pen) if str(pen or "").isdigit() else 0,
        "n_sanciones": int(san_dato) if str(san_dato or "").isdigit() else n_san,
        "actualizado_al": (d.get("dataInfo") or {}).get("updatedTo", "")[:10],
        "url_ficha": cfg.oece["ficha_publica"].format(ruc=ruc),
    }


def fichas(rucs: list[str], cfg: Config | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    cli = Cliente(cfg, espera=cfg.oece["segundos_entre_fichas"])
    destino = cfg.processed_dir / "proveedores_oece.parquet"
    previas = pd.read_parquet(destino) if destino.exists() else pd.DataFrame(columns=["ruc"])
    pendientes = [r for r in dict.fromkeys(rucs) if r not in set(previas["ruc"])]
    log.info("Fichas OECE: %d RUC, %d ya consultados, %d pendientes",
             len(set(rucs)), len(rucs) - len(pendientes), len(pendientes))
    filas = []
    for i, ruc in enumerate(pendientes, 1):
        try:
            filas.append(ficha_proveedor(cli, cfg, ruc))
        except Exception as e:  # noqa: BLE001 - un RUC que falla no corta el lote
            log.warning("  ficha %s fallo: %s", ruc, str(e)[:100])
        if i % 100 == 0 or i == len(pendientes):
            log.info("  fichas %d/%d", i, len(pendientes))
            # Se guarda por bloques: un corte no pierde lo ya consultado.
            tabla = pd.concat([previas, pd.DataFrame(filas)], ignore_index=True)
            tabla.to_parquet(destino, index=False)
    return pd.read_parquet(destino) if destino.exists() else pd.DataFrame()


# --- 03.9 Salida: contratos_vigilancia y experiencia_publica en data/processed
def ejecutar(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    log = configurar_logging("garita.oece")
    cli = Cliente(cfg)
    log.info("OECE: descargando %d meses", len(cfg.oece["meses"]))
    zips = descargar_meses(cfg, cli)
    partes = []
    for z in zips:
        p = procesos_de_vigilancia(z, cfg)
        log.info("  %s: %d procesos de vigilancia", z.name[:7], len(p))
        partes.append(p)
    contratos = limpiar_contratos(pd.concat(partes, ignore_index=True))
    exp = experiencia_publica(contratos)
    contratos.to_parquet(cfg.processed_dir / "contratos_vigilancia.parquet", index=False)
    exp.to_parquet(cfg.processed_dir / "experiencia_publica.parquet", index=False)
    resumen = {
        "meses": [f"{m['anio']}-{m['mes']}" for m in cfg.oece["meses"]],
        "procesos": int(len(contratos)),
        "con_contrato": int(contratos["con_contrato"].sum()),
        "con_bases": int(contratos["url_bases"].notna().sum()),
        "proveedores_con_ruc": int(len(exp)),
    }
    log.info("OECE listo: %s", resumen)
    return resumen


if __name__ == "__main__":
    ejecutar()
