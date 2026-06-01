"""
Restaura hcs_procesadas desde el JSON maestro clínico.

Uso:
    python scripts/restore_json_maestro.py [--dry-run]

Qué hace:
    1. Lee api/hcd/data/json_maestro_hc_salud_mental.json
    2. Construye el resumen en el formato que espera /hcd/reporte-total
    3. Inserta una fila en hcs_procesadas con pseudónimos — sin DNI, nombre ni codigo_hc
    4. Migra internaciones_episodios al esquema C-3 si todavía tiene el esquema viejo
    5. Valida la inserción con SELECT COUNT(*) y verificación de consistencia
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.pseudonimizacion import pseudonymize_identifier, pseudonimizar_texto

# ── Rutas ──────────────────────────────────────────────────────────────────────
JSON_MAESTRO = ROOT / "api" / "hcd" / "data" / "json_maestro_hc_salud_mental.json"
DB_PATH      = ROOT / "hcs.db"


# ── Migración de internaciones_episodios al esquema C-3 ────────────────────────

_SCHEMA_NUEVO = """
    CREATE TABLE internaciones_episodios (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        id_episodio    TEXT    NOT NULL,
        paciente_id    TEXT    NOT NULL,
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
    )
"""

_PII_COLS = {"documento", "codigo_hc", "paciente"}


def _necesita_migracion(con: sqlite3.Connection) -> bool:
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(internaciones_episodios)"
    ).fetchall()}
    return bool(cols & _PII_COLS)


def _migrar_internaciones(con: sqlite3.Connection, dry_run: bool) -> None:
    count = con.execute(
        "SELECT COUNT(*) FROM internaciones_episodios"
    ).fetchone()[0]
    if count > 0:
        print(f"  ADVERTENCIA: internaciones_episodios tiene {count} filas con esquema viejo.")
        print("  No se migra automáticamente. Borrá manualmente y reprocesá los CSVs.")
        return

    print("  internaciones_episodios: esquema viejo, tabla vacía → recreando con esquema C-3")
    if not dry_run:
        con.execute("DROP TABLE internaciones_episodios")
        con.execute(_SCHEMA_NUEVO)
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_int_ep_periodo "
            "ON internaciones_episodios(periodo)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_int_ep_pid "
            "ON internaciones_episodios(paciente_id)"
        )
        con.commit()
        print("  internaciones_episodios: migrado al esquema C-3 ✓")


# ── Construcción del resumen ───────────────────────────────────────────────────

def _construir_resumen(maestro: dict) -> dict:
    carga  = maestro.get("carga_asistencial", {})
    areas  = maestro.get("intervenciones_por_area", {})
    total  = carga.get("total_intervenciones", 0)
    s_areas = sum(areas.values())

    if total == 0:
        raise ValueError("JSON maestro: total_intervenciones = 0")
    if s_areas != total:
        raise ValueError(
            f"Inconsistencia: sum(intervenciones_por_area)={s_areas} != total_intervenciones={total}"
        )

    return {
        "total_intervenciones":       total,
        "total_registros_raw":        total,
        "internacion":                maestro.get("internacion", {}),
        "modelo_nlp":                 maestro.get("modelo_nlp", {}),
        "intervenciones_por_area":    areas,
        "variables_clinicas_detectadas": maestro.get("variables_clinicas_detectadas", {}),
        "interconsultas_detectadas":  maestro.get("interconsultas_detectadas", []),
        "estrategia_externacion":     maestro.get("estrategia_externacion", {}),
        # Bloque paciente: usado internamente por _best_patient_identifier
        # para derivar el PAC-XXXXXXXX; sanitize_public_payload lo redacta en respuestas públicas
        "paciente": maestro.get("paciente", {}),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main(dry_run: bool = False) -> None:
    print(f"{'[DRY-RUN] ' if dry_run else ''}restore_json_maestro.py")
    print(f"  JSON maestro : {JSON_MAESTRO}")
    print(f"  Base de datos: {DB_PATH}")
    print()

    # ── Cargar JSON maestro ──────────────────────────────────────────────────
    if not JSON_MAESTRO.exists():
        sys.exit(f"ERROR: no se encontró {JSON_MAESTRO}")
    with open(JSON_MAESTRO, encoding="utf-8") as f:
        maestro = json.load(f)

    paciente_id_fuente = maestro.get("paciente", {}).get("paciente_id", "HC_001")
    print(f"  paciente_id en maestro  : {paciente_id_fuente}")

    # ── Construir valores a insertar ─────────────────────────────────────────
    resumen      = _construir_resumen(maestro)
    archivo_pseu = pseudonymize_identifier(paciente_id_fuente, prefix="DOC")
    texto_extr   = pseudonimizar_texto(
        "Historia clínica de salud mental. Internación prolongada con seguimiento "
        "psiquiátrico, psicológico, de enfermería, trabajo social y terapia ocupacional."
    )
    fecha        = datetime.datetime.now().isoformat()

    print(f"  archivo pseudonimizado  : {archivo_pseu}")
    print(f"  total_intervenciones    : {resumen['total_intervenciones']}")
    print(f"  sum(intervenciones_area): {sum(resumen['intervenciones_por_area'].values())}")
    print(f"  dias_internacion        : {resumen['internacion'].get('dias_totales')}")
    print(f"  reingresos              : {resumen['internacion'].get('reingresos')}")
    print(f"  variables clínicas      : {sum(1 for v in resumen['variables_clinicas_detectadas'].values() if v)}")
    print(f"  interconsultas          : {len(resumen['interconsultas_detectadas'])}")
    print()

    # ── Operar sobre la BD ───────────────────────────────────────────────────
    if not DB_PATH.exists():
        print(f"  ADVERTENCIA: {DB_PATH} no existe — se creará.")

    con = sqlite3.connect(str(DB_PATH))

    # Verificar/migrar internaciones_episodios
    tablas = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "internaciones_episodios" in tablas and _necesita_migracion(con):
        _migrar_internaciones(con, dry_run)
    elif "internaciones_episodios" in tablas:
        print("  internaciones_episodios: esquema C-3 OK ✓")

    # Verificar duplicado por archivo
    ya_existe = con.execute(
        "SELECT COUNT(*) FROM hcs_procesadas WHERE archivo = ?", (archivo_pseu,)
    ).fetchone()[0]
    if ya_existe:
        print(f"  ADVERTENCIA: ya existe una fila con archivo={archivo_pseu}. Se omite la inserción.")
        print("  Para reinsertar, primero ejecutá: DELETE FROM hcs_procesadas;")
        con.close()
        return

    # Insertar
    if not dry_run:
        con.execute(
            "INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
            (archivo_pseu, json.dumps(resumen, ensure_ascii=False), texto_extr, fecha),
        )
        con.commit()
        print("  INSERT en hcs_procesadas: OK ✓")
    else:
        print("  [DRY-RUN] INSERT en hcs_procesadas: no ejecutado")

    # ── Validación ───────────────────────────────────────────────────────────
    count = con.execute("SELECT COUNT(*) FROM hcs_procesadas").fetchone()[0]
    print(f"\n  SELECT COUNT(*) FROM hcs_procesadas = {count}")

    if not dry_run:
        row = con.execute(
            "SELECT id, archivo, resumen, fecha FROM hcs_procesadas ORDER BY id DESC LIMIT 1"
        ).fetchone()
        d = json.loads(row[2])
        total_ok  = d.get("total_intervenciones", 0) > 0
        areas_ok  = sum(d.get("intervenciones_por_area", {}).values()) == d.get("total_intervenciones", 0)
        pac_ok    = bool(d.get("paciente", {}).get("paciente_id"))
        pii_libre = not any(k in d for k in ("documento", "dni", "nombre_real"))
        print(f"  total_intervenciones > 0     : {'OK ✓' if total_ok  else 'FALLO ✗'}")
        print(f"  sum(areas) == total          : {'OK ✓' if areas_ok  else 'FALLO ✗'}")
        print(f"  paciente_id presente         : {'OK ✓' if pac_ok    else 'FALLO ✗'}")
        print(f"  sin DNI/nombre en resumen    : {'OK ✓' if pii_libre else 'FALLO ✗'}")
        assert total_ok and areas_ok and pac_ok and pii_libre, "Validación fallida"

    con.close()
    print()
    print("  Listo. Verificá con:")
    print("    curl http://localhost:8000/hcd/reporte-total | python3 -m json.tool")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Mostrar plan sin modificar la BD")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
