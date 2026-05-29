"""
Módulo de análisis de internaciones — Servicio de Salud Mental HISJB.

Fuente de verdad: archivos CSV exportados de VADIGU (un archivo por día).
Los PDF se ignoran en esta versión para el cálculo de egresos.

Episodio: estancia continua de un paciente identificada por
          (documento_normalizado, fecha_ingreso).

Indicadores calculados:
    ingresos · egresos · pacientes únicos · pacientes recurrentes
    reingresos ≤ 30 días · días-cama · estancia promedio
"""

import hashlib
import pathlib
import re
import sqlite3
from datetime import date, datetime
from typing import Union

import pandas as pd

from pipeline.censo.modulo_censo_mensual import leer_archivo_censo, clasificar_tipo_cama

# ── Constantes ────────────────────────────────────────────────────────────────

UMBRAL_REINGRESO_DIAS = 30

DB_PATH_DEFAULT = pathlib.Path(__file__).resolve().parents[2] / "hcs.db"

# Columnas de movimiento de camas presentes en los CSV de VADIGU
_COLS_MOVIMIENTO = {"ingresos", "egresos", "egresos_alta", "egresos_obito",
                    "existencia0", "existencia24"}


# ── Helpers internos ──────────────────────────────────────────────────────────

def _fecha_desde_nombre(nombre: str) -> date | None:
    """Extrae fecha de 'Censo Diario DD-MM-YYYY 2011.csv' → date."""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', nombre)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _parsear_ingreso(valor: str) -> date | None:
    """'03/09/2024 18:41:00' o '03/09/2024' → date(2024, 9, 3)."""
    s = re.sub(r'\s+', ' ', str(valor or "")).strip()
    # Extraer solo la parte de fecha (primeros 10 caracteres DD/MM/YYYY)
    if "/" not in s:
        return None
    try:
        return datetime.strptime(s[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def _normalizar_doc(doc: str) -> str:
    """Normaliza el campo Documento a mayúsculas con espacio simple."""
    return re.sub(r'\s+', ' ', str(doc or "")).strip().upper()


def _es_flag_activo(valor) -> bool:
    """Devuelve True si el campo de movimiento vale '1' o 1."""
    return str(valor).strip() == "1"


def _id_episodio(documento: str, fecha_ingreso: date) -> str:
    """Hash SHA-256 truncado a 12 hex — identificador anónimo del episodio."""
    raw = f"{documento}|{fecha_ingreso.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── Selección de archivos CSV ─────────────────────────────────────────────────

def seleccionar_csvs(directorio: pathlib.Path) -> dict[date, pathlib.Path]:
    """
    Devuelve {fecha: ruta} para cada día único del directorio.
    Solo archivos .csv con patrón DD-MM-YYYY en el nombre.
    Ante duplicados del mismo día, prefiere el que no contiene '(1)'.
    """
    por_dia: dict[date, list[pathlib.Path]] = {}
    for ruta in sorted(directorio.glob("*.csv")):
        fecha = _fecha_desde_nombre(ruta.name)
        if fecha:
            por_dia.setdefault(fecha, []).append(ruta)

    seleccion: dict[date, pathlib.Path] = {}
    for fecha, candidatos in por_dia.items():
        limpios = [r for r in candidatos if "(1)" not in r.name]
        seleccion[fecha] = limpios[0] if limpios else candidatos[0]
    return seleccion


# ── Lectura SM con columnas de movimiento ─────────────────────────────────────

def _leer_sm_raw(ruta: pathlib.Path) -> pd.DataFrame:
    """
    Lee todas las filas de Area=Salud Mental del CSV (ocupadas Y libres).
    Conservar filas libres permite capturar egresos del día donde
    el paciente puede aparecer con Estado='Libre' tras ser dado de alta.
    Agrega columna tipo_cama.
    """
    df = leer_archivo_censo(ruta)
    if "Area" not in df.columns:
        return pd.DataFrame()

    mask = df["Area"].map(
        lambda v: re.sub(r'\s+', ' ', str(v)).strip().lower()
    ) == "salud mental"
    df_sm = df[mask].copy()

    if "Cama" in df_sm.columns:
        df_sm["tipo_cama"] = df_sm["Cama"].map(clasificar_tipo_cama)

    return df_sm


# ── Construcción de episodios ─────────────────────────────────────────────────

def _construir_episodios(archivos: dict[date, pathlib.Path]) -> list[dict]:
    """
    Recorre los CSV en orden cronológico y construye un episodio por cada
    combinación única (documento, fecha_ingreso).

    Trazabilidad: cada episodio registra el archivo CSV de ingreso
    y, si se detecta, el archivo CSV donde se leyó el egreso.
    """
    episodios: dict[tuple, dict] = {}

    for fecha_archivo in sorted(archivos):
        ruta = archivos[fecha_archivo]
        df_sm = _leer_sm_raw(ruta)
        if df_sm.empty:
            continue

        for _, fila in df_sm.iterrows():
            doc = _normalizar_doc(fila.get("Documento", ""))
            fecha_ing = _parsear_ingreso(fila.get("Ingreso", ""))
            if not doc or not fecha_ing:
                continue

            key = (doc, fecha_ing)

            if key not in episodios:
                episodios[key] = {
                    # Identificadores
                    "documento":   doc,
                    "codigo_hc":   re.sub(r'\s+', '', str(fila.get("codigoHC", ""))),
                    "paciente":    str(fila.get("Paciente") or "").strip(),
                    # Ubicación
                    "cama":        str(fila.get("Cama", "")).strip(),
                    "tipo_cama":   str(fila.get("tipo_cama", "")).strip(),
                    # Fechas
                    "fecha_ingreso": fecha_ing,
                    "fecha_egreso":  None,
                    "estada_dias":   None,
                    # Estado
                    "activo":        True,
                    "reingreso":     False,
                    # Trazabilidad
                    "fuente_ingreso": ruta.name,
                    "fuente_egreso":  None,
                    "_ultima_fecha_vista": fecha_archivo,
                }

            ep = episodios[key]

            # Actualizar estada (crece día a día) y cama (puede cambiar)
            estada_raw = str(fila.get("Estada", "") or "").strip()
            if estada_raw.isdigit():
                ep["estada_dias"] = int(estada_raw)

            ep["cama"]      = str(fila.get("Cama", ep["cama"])).strip() or ep["cama"]
            ep["tipo_cama"] = str(fila.get("tipo_cama", ep["tipo_cama"])).strip() or ep["tipo_cama"]
            ep["_ultima_fecha_vista"] = fecha_archivo

            # Detectar egreso: egresos_alta (alta médica) o egresos_obito (fallecimiento)
            # Solo se registra una vez (el primer archivo donde aparece el flag)
            if ep["fecha_egreso"] is None:
                egresado = (
                    _es_flag_activo(fila.get("egresos_alta", 0))
                    or _es_flag_activo(fila.get("egresos_obito", 0))
                )
                if egresado:
                    ep["fecha_egreso"] = fecha_archivo
                    ep["fuente_egreso"] = ruta.name
                    ep["activo"]       = False

    return list(episodios.values())


# ── Detección de reingresos ───────────────────────────────────────────────────

def _detectar_reingresos(
    episodios: list[dict],
    umbral: int = UMBRAL_REINGRESO_DIAS,
) -> list[dict]:
    """
    Marca reingreso=True cuando el ingreso de un episodio ocurre dentro de
    `umbral` días del egreso del episodio anterior del mismo paciente.
    Solo computable cuando el episodio previo tiene fecha_egreso conocida.
    """
    por_paciente: dict[str, list[dict]] = {}
    for ep in episodios:
        por_paciente.setdefault(ep["documento"], []).append(ep)

    for eps in por_paciente.values():
        eps.sort(key=lambda e: e["fecha_ingreso"])
        for i in range(1, len(eps)):
            prev = eps[i - 1]
            curr = eps[i]
            if prev["fecha_egreso"] is None:
                continue  # gap incalculable, no se marca
            gap = (curr["fecha_ingreso"] - prev["fecha_egreso"]).days
            if 0 <= gap <= umbral:
                curr["reingreso"] = True

    return episodios


# ── Indicadores ───────────────────────────────────────────────────────────────

def calcular_indicadores(episodios: list[dict], n_archivos: int = 0) -> dict:
    """
    Calcula todos los indicadores mensuales a partir de la lista de episodios.
    Función pública para reutilización desde la API y tests.
    """
    count_por_doc: dict[str, int] = {}
    for ep in episodios:
        count_por_doc[ep["documento"]] = count_por_doc.get(ep["documento"], 0) + 1

    estadas = [ep["estada_dias"] for ep in episodios if ep["estada_dias"] is not None]
    dias_cama = sum(estadas)

    return {
        "total_ingresos":         len(episodios),
        "total_egresos":          sum(1 for ep in episodios if ep["fecha_egreso"] is not None),
        "pacientes_unicos":       len(count_por_doc),
        "pacientes_recurrentes":  sum(1 for c in count_por_doc.values() if c > 1),
        "total_reingresos_30d":   sum(1 for ep in episodios if ep["reingreso"]),
        "porcentaje_reingresos":  round(
            100 * sum(1 for ep in episodios if ep["reingreso"]) / len(episodios), 1
        ) if episodios else 0.0,
        "dias_cama_utilizados":   dias_cama,
        "estancia_promedio_dias": round(dias_cama / len(estadas), 1) if estadas else 0.0,
        "internaciones_activas":  sum(1 for ep in episodios if ep["activo"]),
        "archivos_csv_procesados": n_archivos,
    }


# ── Persistencia ──────────────────────────────────────────────────────────────

def _init_tablas(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS internaciones_episodios (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            id_episodio    TEXT    NOT NULL,
            documento      TEXT    NOT NULL,
            codigo_hc      TEXT,
            paciente       TEXT,
            cama           TEXT,
            tipo_cama      TEXT,
            fecha_ingreso  TEXT,
            fecha_egreso   TEXT,
            estada_dias    INTEGER,
            activo         INTEGER,
            reingreso      INTEGER,
            fuente_ingreso TEXT,
            fuente_egreso  TEXT,
            periodo        TEXT    NOT NULL,
            procesado_en   TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_int_ep_periodo
            ON internaciones_episodios(periodo);
        CREATE INDEX IF NOT EXISTS idx_int_ep_doc
            ON internaciones_episodios(documento);

        CREATE TABLE IF NOT EXISTS internaciones_indicadores (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo                 TEXT    UNIQUE NOT NULL,
            total_ingresos          INTEGER,
            total_egresos           INTEGER,
            pacientes_unicos        INTEGER,
            pacientes_recurrentes   INTEGER,
            total_reingresos_30d    INTEGER,
            porcentaje_reingresos   REAL,
            dias_cama_utilizados    INTEGER,
            estancia_promedio_dias  REAL,
            internaciones_activas   INTEGER,
            archivos_csv_procesados INTEGER,
            generado_en             TEXT
        );
    """)
    con.commit()


def _persistir(
    episodios: list[dict],
    indicadores: dict,
    periodo: str,
    db_path: pathlib.Path,
) -> None:
    """Guarda episodios e indicadores en hcs.db (idempotente por período)."""
    con = sqlite3.connect(str(db_path))
    _init_tablas(con)

    # Reemplazar datos del período completo para que el reprocesado sea limpio
    con.execute("DELETE FROM internaciones_episodios WHERE periodo = ?", (periodo,))

    ahora = datetime.now().isoformat()
    for ep in episodios:
        con.execute(
            """INSERT INTO internaciones_episodios
               (id_episodio, documento, codigo_hc, paciente, cama, tipo_cama,
                fecha_ingreso, fecha_egreso, estada_dias, activo, reingreso,
                fuente_ingreso, fuente_egreso, periodo, procesado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _id_episodio(ep["documento"], ep["fecha_ingreso"]),
                ep["documento"],
                ep["codigo_hc"],
                ep["paciente"],
                ep["cama"],
                ep["tipo_cama"],
                ep["fecha_ingreso"].isoformat() if ep["fecha_ingreso"] else None,
                ep["fecha_egreso"].isoformat()  if ep["fecha_egreso"]  else None,
                ep["estada_dias"],
                1 if ep["activo"]    else 0,
                1 if ep["reingreso"] else 0,
                ep["fuente_ingreso"],
                ep["fuente_egreso"],
                periodo,
                ahora,
            ),
        )

    con.execute(
        """INSERT OR REPLACE INTO internaciones_indicadores
           (periodo, total_ingresos, total_egresos, pacientes_unicos,
            pacientes_recurrentes, total_reingresos_30d, porcentaje_reingresos,
            dias_cama_utilizados, estancia_promedio_dias, internaciones_activas,
            archivos_csv_procesados, generado_en)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            periodo,
            indicadores["total_ingresos"],
            indicadores["total_egresos"],
            indicadores["pacientes_unicos"],
            indicadores["pacientes_recurrentes"],
            indicadores["total_reingresos_30d"],
            indicadores["porcentaje_reingresos"],
            indicadores["dias_cama_utilizados"],
            indicadores["estancia_promedio_dias"],
            indicadores["internaciones_activas"],
            indicadores["archivos_csv_procesados"],
            ahora,
        ),
    )
    con.commit()
    con.close()


# ── Función principal pública ─────────────────────────────────────────────────

def procesar_mes(
    directorio: Union[str, pathlib.Path],
    periodo: str,
    umbral_reingreso: int = UMBRAL_REINGRESO_DIAS,
    db_path: Union[str, pathlib.Path, None] = None,
) -> dict:
    """
    Lee todos los CSV del directorio, construye episodios, calcula
    indicadores y persiste en hcs.db.

    Args:
        directorio:       carpeta con archivos de censo (CSV priorizados).
        periodo:          "YYYY-MM" (ej. "2026-05").
        umbral_reingreso: días máximos egreso→ingreso para contar reingreso.
        db_path:          ruta a hcs.db; None usa la ruta del proyecto.

    Returns:
        {"episodios": [...], "indicadores": {...},
         "periodo": str, "advertencias": [...]}
    """
    directorio = pathlib.Path(directorio).expanduser()
    db_path    = pathlib.Path(db_path).expanduser() if db_path else DB_PATH_DEFAULT

    archivos     = seleccionar_csvs(directorio)
    advertencias: list[str] = []

    if not archivos:
        advertencias.append(
            f"No se encontraron CSV con patrón DD-MM-YYYY en: {directorio}"
        )
        return {"episodios": [], "indicadores": {}, "periodo": periodo,
                "advertencias": advertencias}

    episodios   = _construir_episodios(archivos)
    episodios   = _detectar_reingresos(episodios, umbral=umbral_reingreso)
    indicadores = calcular_indicadores(episodios, n_archivos=len(archivos))

    _persistir(episodios, indicadores, periodo, db_path)

    # Serializar fechas y ocultar documento para la respuesta
    episodios_out = [_serializar(ep, periodo) for ep in episodios]

    return {
        "episodios":    episodios_out,
        "indicadores":  indicadores,
        "periodo":      periodo,
        "advertencias": advertencias,
    }


def _serializar(ep: dict, periodo: str) -> dict:
    """Convierte un episodio interno en dict JSON-serializable sin el DNI."""
    return {
        "id_episodio":   _id_episodio(ep["documento"], ep["fecha_ingreso"]),
        "cama":          ep["cama"],
        "tipo_cama":     ep["tipo_cama"],
        "fecha_ingreso": ep["fecha_ingreso"].isoformat() if ep["fecha_ingreso"] else None,
        "fecha_egreso":  ep["fecha_egreso"].isoformat()  if ep["fecha_egreso"]  else None,
        "estada_dias":   ep["estada_dias"],
        "activo":        ep["activo"],
        "reingreso":     ep["reingreso"],
        "fuente_ingreso": ep["fuente_ingreso"],
        "fuente_egreso":  ep["fuente_egreso"],
        "periodo":        periodo,
    }


# ── Funciones de consulta (lectura desde DB) ──────────────────────────────────

def indicadores_periodo(
    periodo: str,
    db_path: Union[str, pathlib.Path, None] = None,
) -> dict | None:
    """Lee los indicadores del período desde la caché en hcs.db."""
    db_path = pathlib.Path(db_path).expanduser() if db_path else DB_PATH_DEFAULT
    con = sqlite3.connect(str(db_path))
    _init_tablas(con)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM internaciones_indicadores WHERE periodo = ?", (periodo,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def episodios_periodo(
    periodo: str,
    db_path: Union[str, pathlib.Path, None] = None,
) -> list[dict]:
    """
    Lista episodios del período sin exponer el campo documento (DNI).
    Devuelve id_episodio, cama, tipo_cama, fechas, estada, activo, reingreso,
    fuentes.
    """
    db_path = pathlib.Path(db_path).expanduser() if db_path else DB_PATH_DEFAULT
    con = sqlite3.connect(str(db_path))
    _init_tablas(con)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id_episodio, cama, tipo_cama, fecha_ingreso, fecha_egreso,
                  estada_dias, activo, reingreso, fuente_ingreso, fuente_egreso
           FROM internaciones_episodios
           WHERE periodo = ?
           ORDER BY fecha_ingreso""",
        (periodo,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def reingresos_periodo(
    periodo: str,
    db_path: Union[str, pathlib.Path, None] = None,
) -> list[dict]:
    """Lista solo los episodios marcados como reingreso en el período."""
    db_path = pathlib.Path(db_path).expanduser() if db_path else DB_PATH_DEFAULT
    con = sqlite3.connect(str(db_path))
    _init_tablas(con)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id_episodio, cama, tipo_cama, fecha_ingreso, fecha_egreso,
                  estada_dias, fuente_ingreso, fuente_egreso
           FROM internaciones_episodios
           WHERE periodo = ? AND reingreso = 1
           ORDER BY fecha_ingreso""",
        (periodo,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def historico_por_hc(
    codigo_hc: str,
    db_path: Union[str, pathlib.Path, None] = None,
) -> list[dict]:
    """
    Historial de episodios de un paciente identificado por su codigoHC
    (no expone el DNI).
    """
    db_path = pathlib.Path(db_path).expanduser() if db_path else DB_PATH_DEFAULT
    con = sqlite3.connect(str(db_path))
    _init_tablas(con)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id_episodio, periodo, cama, tipo_cama, fecha_ingreso,
                  fecha_egreso, estada_dias, activo, reingreso
           FROM internaciones_episodios
           WHERE codigo_hc = ?
           ORDER BY fecha_ingreso""",
        (codigo_hc,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]
