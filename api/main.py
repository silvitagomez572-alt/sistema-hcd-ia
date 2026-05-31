import json
import os
import pathlib
import io
import re
import httpx
import chromadb
import pypdf
from chromadb.utils import embedding_functions
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import datetime as dt_module
from zoneinfo import ZoneInfo

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")
BASE_DIR = pathlib.Path(__file__).resolve().parent
_MOBILE_UPLOAD_DIR = BASE_DIR.parent / "uploads" / "censos"
_MOBILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
HCD_PATH = BASE_DIR / "hcd" / "data" / "json_maestro_hc_salud_mental.json"

app = FastAPI(title="Sistema HCD IA", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def load_hcd():
    with open(HCD_PATH, encoding="utf-8") as f:
        return json.load(f)

@app.get("/health")
def health():
    return {"status": "ok", "time": dt_module.datetime.now(AR_TZ).isoformat()}

@app.get("/hcd/summary")
def hcd_summary():
    return sanitize_public_payload(load_hcd())

@app.get("/hcd/interconsultas")
def hcd_interconsultas():
    return sanitize_public_payload(load_hcd()["interconsultas_detectadas"])

@app.get("/hcd/metricas")
def hcd_metricas():
    data = load_hcd()
    return sanitize_public_payload({"modelo_nlp": data["modelo_nlp"], "carga_asistencial": data["carga_asistencial"], "intervenciones_por_area": data["intervenciones_por_area"], "internacion": data["internacion"], "variables_clinicas_detectadas": data["variables_clinicas_detectadas"], "estrategia_externacion": data["estrategia_externacion"]})

@app.post("/llm/consultar")
async def llm_consultar(payload: dict):
    pregunta = payload.get("pregunta", "")
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": f"Eres un asistente clinico hospitalario. Responde en espanol. {pregunta}", "stream": False})
        data = r.json()
        return {"respuesta": data.get("response", "")}

_chroma_client = None
_collection = None

def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _chroma_client = chromadb.PersistentClient(path="rag/db")
        _collection = _chroma_client.get_collection(name="protocolos_clinicos", embedding_function=ef)
    return _collection

@app.post("/rag/consultar")
async def rag_consultar(payload: dict):
    pregunta = payload.get("pregunta", "")
    collection = get_collection()
    resultados = collection.query(query_texts=[pregunta], n_results=1)
    contexto = resultados["documents"][0][0][:500]
    prompt = f"Contexto: {contexto}. Pregunta breve: {pregunta}. Responde en 2 oraciones en espanol."
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
        data = r.json()
        return {"respuesta": data.get("response", ""), "fuentes": resultados["metadatas"][0]}

RAG_PROTOCOLOS_DIR = BASE_DIR.parent / "rag" / "protocolos"

@app.get("/rag/documentos")
def rag_documentos():
    RAG_PROTOCOLOS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        collection = get_collection()
        metas = collection.get(include=["metadatas"])["metadatas"]
        indexados = {m["fuente"] for m in metas if "fuente" in m}
    except Exception:
        indexados = set()
    docs = []
    for f in sorted(RAG_PROTOCOLOS_DIR.iterdir()):
        if f.is_file():
            docs.append({
                "nombre": f.name,
                "tipo": f.suffix.upper().lstrip("."),
                "tamano_kb": round(f.stat().st_size / 1024, 1),
                "indexado": f.name in indexados,
            })
    return docs

def _extraer_texto_pdf(contenido: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(contenido))
    return "".join(page.extract_text() or "" for page in reader.pages)

def _indexar_documento(nombre: str, contenido: bytes, sufijo: str) -> int:
    if sufijo == ".pdf":
        texto = _extraer_texto_pdf(contenido)
    elif sufijo == ".txt":
        texto = contenido.decode("utf-8", errors="replace")
    else:
        return 0
    texto = texto.strip()
    if not texto:
        return 0
    stem = pathlib.Path(nombre).stem
    chunks = [texto[i:i+500] for i in range(0, len(texto), 500)]
    chunks = [c for c in chunks if c.strip()]
    collection = get_collection()
    collection.upsert(
        documents=chunks,
        ids=[f"{stem}_{j}" for j in range(len(chunks))],
        metadatas=[{"fuente": nombre}] * len(chunks),
    )
    return len(chunks)

@app.post("/rag/subir")
async def rag_subir(archivo: UploadFile = File(...)):
    RAG_PROTOCOLOS_DIR.mkdir(parents=True, exist_ok=True)
    sufijo = pathlib.Path(archivo.filename).suffix.lower()
    if sufijo not in {".pdf", ".txt", ".docx"}:
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {sufijo}")
    contenido = await archivo.read()
    destino = RAG_PROTOCOLOS_DIR / archivo.filename
    with open(destino, "wb") as out:
        out.write(contenido)
    try:
        n_chunks = _indexar_documento(archivo.filename, contenido, sufijo)
        return {"archivo": archivo.filename, "estado": "indexado", "indexado": True, "chunks": n_chunks}
    except Exception as e:
        return {"archivo": archivo.filename, "estado": "guardado_sin_indexar", "indexado": False, "error": str(e)}

from bs4 import BeautifulSoup
import xlrd, openpyxl, io
from pipeline.pseudonimizacion import (
    generar_paciente_id,
    pseudonimizar_texto,
    pseudonymize_identifier,
    sanitize_public_payload,
)


def _loads_public_summary(resumen_raw):
    try:
        return sanitize_public_payload(json.loads(resumen_raw))
    except Exception:
        return {"resumen": pseudonimizar_texto(resumen_raw)}


def _public_summary_json(resumen_raw):
    return json.dumps(_loads_public_summary(resumen_raw), ensure_ascii=False)


def _best_patient_identifier(row_id, archivo, resumen=None, texto_extraido=""):
    resumen = resumen if isinstance(resumen, dict) else {}
    paciente = resumen.get("paciente", {})
    if isinstance(paciente, dict) and paciente.get("paciente_id"):
        return paciente["paciente_id"]
    combined = " ".join(str(x or "") for x in (texto_extraido, archivo))
    for pattern in (r"\b\d{1,5}-\d{6,9}-\d{1,3}\b", r"\b\d{7,8}\b"):
        match = re.search(pattern, combined)
        if match:
            return match.group(0)
    return archivo or f"ROW-{row_id}"


def _codigo_paciente(row_id, archivo, resumen=None, texto_extraido=""):
    return generar_paciente_id(_best_patient_identifier(row_id, archivo, resumen, texto_extraido))


def _archivo_publico(nombre_archivo):
    return pseudonymize_identifier(nombre_archivo, prefix="DOC")


def _normalizar_busqueda(valor):
    return re.sub(r"[^a-z0-9]", "", str(valor or "").lower())


def _coincide_identificador(consulta, *campos):
    consulta_txt = str(consulta or "").strip().lower()
    consulta_norm = _normalizar_busqueda(consulta)
    if not consulta_txt and not consulta_norm:
        return False
    for campo in campos:
        campo_txt = str(campo or "").lower()
        campo_norm = _normalizar_busqueda(campo)
        if consulta_txt and consulta_txt in campo_txt:
            return True
        if consulta_norm and consulta_norm in campo_norm:
            return True
    return False

@app.post("/hcd/procesar")
async def procesar_hc(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    # Extraer texto segun formato
    if archivo.filename.endswith((".xls", ".xlsx")):
        import io
        if archivo.filename.endswith(".xls"):
            # VADIGU exporta HTML disfrazado de XLS
            soup = BeautifulSoup(contenido, "html.parser")
            texto = soup.get_text(separator=" | ", strip=True)[:500]
        else:
            wb = openpyxl.load_workbook(io.BytesIO(contenido))
            filas = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    filas.append(" | ".join(str(c) for c in row if c))
            texto = chr(10).join(filas)[:2000]
    else:
        soup = BeautifulSoup(contenido, "html.parser")
        texto = soup.get_text(separator=" ", strip=True)[:2000]
    texto_publico = pseudonimizar_texto(texto)
    prompt = f"""Eres un asistente clinico hospitalario. Analiza esta historia clinica pseudonimizada y extrae en espanol:
1. Datos clinicos generales disponibles (edad si aparece, servicio)
2. Principales intervenciones detectadas
3. Areas involucradas
4. Variables clinicas relevantes
Historia clinica: {texto_publico}
Responde de forma estructurada y breve."""
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
        data = r.json()
        resumen = pseudonimizar_texto(data.get("response", ""))
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
            (archivo.filename, resumen, texto_publico[:500], datetime.datetime.now().isoformat()))
        con.commit()
        con.close()
        return {"archivo": _archivo_publico(archivo.filename), "resumen": resumen}

import sqlite3, datetime

DB_PATH = "hcs.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS hcs_procesadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archivo TEXT,
        resumen TEXT,
        texto_extraido TEXT,
        fecha TEXT
    )""")
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
    con.close()

init_db()

@app.get("/hcd/reportes")
def get_reportes():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, archivo, resumen, texto_extraido, fecha FROM hcs_procesadas ORDER BY fecha DESC").fetchall()
    con.close()
    result = []
    for r in rows:
        resumen = _loads_public_summary(r[2])
        result.append({
            "id": r[0],
            "archivo": _archivo_publico(r[1]),
            "resumen": json.dumps(resumen, ensure_ascii=False),
            "fecha": r[4],
            "codigo_paciente": _codigo_paciente(r[0], r[1], resumen, r[3]),
        })
    return result


@app.post("/hcd/buscar-interno")
def buscar_hc_interno(payload: dict):
    """
    Lookup operativo: acepta DNI/nombre/codigoHC/archivo para matching interno,
    pero nunca devuelve esos identificadores crudos.
    """
    consulta = payload.get("q") or payload.get("identificador") or payload.get("codigo_hc") or payload.get("dni") or payload.get("nombre")
    if not str(consulta or "").strip():
        return {"encontrado": False}

    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id, archivo, resumen, texto_extraido, fecha FROM hcs_procesadas ORDER BY fecha DESC"
    ).fetchall()
    con.close()

    for r in rows:
        if not _coincide_identificador(consulta, r[1], r[2], r[3]):
            continue
        resumen = _loads_public_summary(r[2])
        return {
            "encontrado": True,
            "codigo_paciente": _codigo_paciente(r[0], r[1], resumen, r[3]),
            "id": r[0],
            "fecha": r[4],
        }

    return {"encontrado": False}

@app.get("/hcd/reporte-total")
def reporte_total():
    con = sqlite3.connect(DB_PATH)
    # Deduplicar: mantener el registro más reciente por archivo
    rows = con.execute(
        "SELECT id, archivo, resumen, fecha, texto_extraido FROM hcs_procesadas "
        "WHERE id IN (SELECT MAX(id) FROM hcs_procesadas GROUP BY archivo) "
        "ORDER BY id"
    ).fetchall()
    con.close()

    casos, areas_global, vars_global, ics_por_estado = [], {}, {}, {}
    total_intervenciones = total_reingresos = 0
    dias_list = []

    for r in rows:
        try:
            d = json.loads(r[2])
        except:
            continue
        codigo = _codigo_paciente(r[0], r[1], d, r[4])
        total_pac = d.get("total_intervenciones", 0)
        intern = d.get("internacion", {})
        dias = intern.get("dias_totales", 0)
        areas = d.get("intervenciones_por_area", {})

        # Registro válido: total_intervenciones > 0 y áreas consistentes
        datos_validos = total_pac > 0 and sum(areas.values()) == total_pac
        if not datos_validos:
            continue

        if dias:
            dias_list.append(dias)
        total_intervenciones += total_pac
        total_reingresos += intern.get("reingresos", 0)

        # Áreas solo de registros válidos (misma lógica que Métricas HCD)
        for k, v in areas.items():
            areas_global[k] = areas_global.get(k, 0) + v

        vars_c = d.get("variables_clinicas_detectadas", {})
        for k, v in vars_c.items():
            if v:
                vars_global[k] = vars_global.get(k, 0) + 1

        area_principal = max(areas, key=areas.get) if areas else "-"
        ics = d.get("interconsultas_detectadas", [])
        ics_efectivas = [ic for ic in ics if ic.get("contar")]
        for ic in ics:
            estado = ic.get("estado_interconsulta", "otro")
            ics_por_estado[estado] = ics_por_estado.get(estado, 0) + len(ic.get("servicios", [1]))

        vars_presentes = [k for k, v in vars_c.items() if v]
        casos.append({
            "codigo_paciente": codigo,
            "archivo": _archivo_publico(r[1]),
            "fecha_procesamiento": r[3][:10],
            "total_intervenciones": total_pac,
            "dias_internacion": dias,
            "reingresos": intern.get("reingresos", 0),
            "area_principal": area_principal,
            "intervenciones_por_area": areas,
            "variables_clinicas_presentes": vars_presentes,
            "interconsultas_efectivas": len(ics_efectivas),
            "interconsultas_total": len(ics),
        })

    n = len(casos)
    return sanitize_public_payload({
        "resumen_ejecutivo": {
            "total_pacientes": n,
            "total_intervenciones": total_intervenciones,
            "promedio_intervenciones_por_paciente": round(total_intervenciones / n, 1) if n else 0,
            "promedio_dias_internacion": round(sum(dias_list) / len(dias_list), 1) if dias_list else 0,
            "total_reingresos": total_reingresos,
            "intervenciones_por_area": areas_global,
        },
        "variables_clinicas_por_frecuencia": dict(sorted(vars_global.items(), key=lambda x: -x[1])),
        "interconsultas_por_estado": ics_por_estado,
        "casos": casos,
    })

@app.delete("/hcd/reportes/duplicados")
def limpiar_duplicados():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        DELETE FROM hcs_procesadas
        WHERE id NOT IN (SELECT MAX(id) FROM hcs_procesadas GROUP BY archivo)
    """)
    eliminados = con.total_changes
    con.commit()
    con.close()
    return {"eliminados": eliminados}

@app.delete("/hcd/reportes/limpiar")
def limpiar_reportes():
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM hcs_procesadas")
    eliminados = con.total_changes
    con.commit()
    con.close()
    return {"eliminados": eliminados}

@app.get("/hcd/reportes/{id}/json")
def reporte_json(id: int):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT id, archivo, resumen, fecha, texto_extraido FROM hcs_procesadas WHERE id = ?", (id,)).fetchone()
    con.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    resumen = _loads_public_summary(row[2])
    return {
        "id": row[0],
        "archivo": _archivo_publico(row[1]),
        "fecha": row[3],
        "codigo_paciente": _codigo_paciente(row[0], row[1], resumen, row[4]),
        "datos": resumen,
    }

@app.get("/hcd/reportes/exportar")
def exportar_reportes():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, archivo, resumen, texto_extraido, fecha FROM hcs_procesadas ORDER BY fecha DESC").fetchall()
    con.close()
    resultado = []
    for r in rows:
        resumen = _loads_public_summary(r[2])
        resultado.append({
            "id": r[0],
            "codigo_paciente": _codigo_paciente(r[0], r[1], resumen, r[3]),
            "archivo": _archivo_publico(r[1]),
            "datos": resumen,
            "fecha": r[4],
        })
    return resultado


import hashlib
import joblib
import re as _re
from collections import Counter

_modelo_nlp = None

def get_modelo():
    global _modelo_nlp
    if _modelo_nlp is None:
        _modelo_nlp = joblib.load("modelo_area_intervenciones.pkl")
    return _modelo_nlp

def generar_id_intervencion(paciente_codigo, fecha, hora, area, tipo_bloque, texto):
    fecha_str = (fecha or "").replace("/", "-")
    hora_str = (hora or "").replace(":", "")
    area_str = (area or "NOASIG").upper()
    tipo_str = (tipo_bloque or "BLOQUE").upper()[:12].replace(" ", "_")
    hash_corto = hashlib.md5(texto.encode("utf-8", errors="ignore")).hexdigest()[:6]
    return f"{paciente_codigo}_{fecha_str}_{hora_str}_{area_str}_{tipo_str}_{hash_corto}"

REGLAS_CONTEO = {
    "CUENTA": [
        "evolucion clinica","evolución clínica",
        "nota de enfermeria","nota de enfermería",
        "seguimiento",
        "interconsulta inicial",
        "reevaluacion","reevaluación",
        "evaluacion psicologica","evaluación psicológica",
        "evaluacion psiquiatrica","evaluación psiquiátrica",
        "trabajo social",
        "acompañamiento terapeutico","acompañamiento terapéutico",
        "terapia ocupacional",
    ],
    "MIN_CHARS": 30,
}

def _criterio_conteo(registro, textos_vistos):
    texto = registro["texto"]
    tipo = (registro["tipo"] or "").lower()
    if len(texto) < REGLAS_CONTEO["MIN_CHARS"]:
        return {"cuenta": False, "motivo": "bloque menor a 30 caracteres", "regla_aplicada": "NO_CUENTA:min_chars"}
    texto_norm = texto.strip().lower()
    if texto_norm in textos_vistos:
        return {"cuenta": False, "motivo": "duplicado exacto", "regla_aplicada": "NO_CUENTA:duplicado"}
    textos_vistos.add(texto_norm)
    for marcador in REGLAS_CONTEO["CUENTA"]:
        if marcador in tipo or marcador in texto.lower()[:150]:
            return {"cuenta": True, "motivo": f"marcador: {marcador}", "regla_aplicada": f"CUENTA:{marcador}"}
    return {"cuenta": False, "motivo": "sin marcador clínico reconocido", "regla_aplicada": "NO_CUENTA:sin_marcador"}

def parsear_intervenciones(texto, paciente_codigo="PAC-XXX"):
    import re
    patron = r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}:\d{2})\s*hs'
    marcadores = ["nota de enfermeria","nota de enfermería","evolucion clinica","evolución clínica","seguimiento","diagnostico","diagnóstico","indicacion","indicación","motivo de consulta"]
    registros = []
    textos_vistos = set()
    fecha_actual = hora_actual = None
    bloque = tipo = ""
    fb = hb = None
    for linea in texto.split("\n"):
        linea = linea.strip()
        m = re.search(patron, linea)
        if m:
            fecha_actual = m.group(1)
            hora_actual = m.group(2)
            continue
        if any(x in linea.lower() for x in marcadores):
            if bloque:
                r = {"fecha": fb, "hora": hb, "tipo": tipo, "texto": bloque.strip()}
                r["id_intervencion"] = generar_id_intervencion(paciente_codigo, fb, hb, "NOASIG", tipo, bloque.strip())
                r["criterio_conteo"] = _criterio_conteo(r, textos_vistos)
                registros.append(r)
            bloque = linea; tipo = linea; fb = fecha_actual; hb = hora_actual
        else:
            if bloque: bloque += " " + linea
    if bloque:
        r = {"fecha": fb, "hora": hb, "tipo": tipo, "texto": bloque.strip()}
        r["id_intervencion"] = generar_id_intervencion(paciente_codigo, fb, hb, "NOASIG", tipo, bloque.strip())
        r["criterio_conteo"] = _criterio_conteo(r, textos_vistos)
        registros.append(r)
    return registros

PROFESIONALES_SALUD_MENTAL = {
    "psiquiatria": ["villagra","gabriela villagra","monjes","heide monjes","zarate","zarate franco","coronel virginia","virginia coronel","luque","palomino"],
    "trabajo_social": ["garribia","garribia romina","pintos juliana","pintos ana julieta","pintos"],
    "acompanante_terapeutico": ["elias nieto","nieto ivan","nieto"],
    "terapia_ocupacional": ["silva maria julia","maria julia silva","julia silva"],
    "psicopedagogia": ["villalba maria del carmen","villalba"],
    "psicologia": ["silva eva","eva argentina","arce mauricio","mauricio arce","arce","pinetta amanda","amanda pinetta","noblega","carrizo sonia","sonia carrizo","carrizo","paez flores","hilen paez","paez","aguero lorena","lorena aguero","aguero","agüero","zuliani","cuello ana","cuello","vera cordoba","paula andrea","cordoba","córdoba","gandini","romero maria elena","romero","valverde","silva maria virginia","silva virginia","fernandez irina","segura ianna","medina celeste"],
    "enfermeria": ["salas silvia","salas silva","correa nancy","vega viviana","ayosa","barrios jorge","collante","romero clelia","luna jose","barrionuevo","aramburu","segobia","herrera ana","ochoa aybar","quispe","vega gordillo","cardenes","maldonado elizabeth","nieva judith"]
}
TODOS_PROFESIONALES_SM = [p for profs in PROFESIONALES_SALUD_MENTAL.values() for p in profs]
SERVICIOS_SALUD_MENTAL = ["psicologia","psicología","psiquiatria","psiquiatría","enfermeria","enfermería","trabajo social","terapia ocupacional","acompañante terapeutico","acompañante terapéutico","salud mental"]
SERVICIOS_EXTERNOS = ["cardiologia","cardiología","cirugia","cirugía","cirugia general","cirugía general","cirugia oncologica","cirugia vascular","cirugía vascular","clinica medica","clínica médica","dermatologia","dermatología","endocrinologia","endocrinología","fonoaudiologia","fonoaudiología","gastroenterologia","gastroenterología","ginecologia","ginecología","hematologia","hematología","infectologia","infectología","kinesiologia","kinesiología","nefrologia","nefrología","neurologia","neurología","nutricion","nutrición","oftalmologia","oftalmología","oncologia","oncología","otorrinolaringologia","traumatologia","traumatología","urologia","urología","uco","odontologia","odontología"]

def detectar_area_por_profesional(nombre_prof):
    """Determina el area de un profesional. None si es externo."""
    nombre_lower = nombre_prof.lower()
    for area, profs in PROFESIONALES_SALUD_MENTAL.items():
        if any(p in nombre_lower for p in profs):
            return area
    return None  # externo = interconsulta

# Prioridad de clasificación: psiquiatria > psicologia > terapia_ocupacional
# > trabajo_social > acompanante_terapeutico > enfermeria > psicopedagogia
# El clasificador itera en orden de inserción del dict y retorna el primer match.
REGLAS_AREA_TEXTO = {
    "psiquiatria": [
        # sustantivo y persona
        "psiquiatria","psiquiatría","psiquiatra","psiquiatras",
        # formas adjetivales (acento en á ≠ acento en í del sustantivo)
        "psiquiátrica","psiquiátrico","psiquiátricas","psiquiátricos",
        "psiquiatrica","psiquiatrico","psiquiatricas","psiquiatricos",
        # frases compuestas
        "guardia de psiquiatria","guardia de psiquiatría",
        "guardia psiquiátrica","guardia psiquiatrica",
        "evaluacion psiquiatrica","evaluación psiquiátrica",
        "medicacion psiquiatrica","medicación psiquiátrica",
        "indicacion psiquiatrica","indicación psiquiátrica",
        "interconsulta psiquiatrica","interconsulta psiquiátrica",
        "consulta psiquiatrica","consulta psiquiátrica",
        "atencion psiquiatrica","atención psiquiátrica",
        "seguimiento psiquiatrico","seguimiento psiquiátrico",
        "conducta psiquiatrica","conducta psiquiátrica",
        "plan psicofarmacologico","plan psicofarmacológico",
        "ajuste psicofarmacologico","ajuste psicofarmacológico",
        # abreviaturas
        "psiq.","psiq ","psiq:",
        # antipsicóticos (altamente específicos de psiquiatría)
        "haloperidol","risperidona","olanzapina","quetiapina","aripiprazol",
        "clozapina","amisulprida","levomepromazina","ziprasidona","paliperidona",
        # estabilizadores del ánimo
        "valproato","valproico","carbonato de litio",
        # benzodiazepinas de uso frecuente en internación psiquiátrica
        "clonazepam","lorazepam",
        # clases de medicación
        "antipsicótico","antipsicotico","antipsicótica","antipsicotica",
        "antipsicóticos","antipsicoticos","antipsicóticas","antipsicoticas",
        "psicofármaco","psicofarmaco","psicofármacos","psicofarmacos",
        "psicofarmacológico","psicofarmacologico",
        "psicofarmacológica","psicofarmacologica",
        "benzodiacepina","benzodiazepina","benzodiacepinas","benzodiazepinas",
        "psicotrópico","psicotropico","psicotrópicos",
        # entrevista y valoración clínica
        "se realiza entrevista directa","se realiza entrevista indirecta",
        "descripcion semiologica","estado psiquico","otep",
        "orientado globalmente","no puede ser entrevistado",
        "manifiesta rechazo al tratamiento",
    ],
    "psicologia": [
        "psicologia","psicología","psicologa","psicólogo","psicóloga",
        "espacio psicologico","espacio psicológico","intervencion psicologica",
        "intervencion psicológica","entrevista psicológica","entrevista psicologica",
        "abordaje psicológico","abordaje psicologico",
        "se realiza contencion","con conciencia de enfermedad","sin conciencia de enfermedad",
    ],
    "terapia_ocupacional": [
        "terapia ocupacional","terapista ocupacional","t.o.","terapeuta ocupacional",
        "taller de to","actividad de to","espacio de to","taller ocupacional",
        "actividades de la vida diaria","avd","actividades ocupacionales"
    ],
    "trabajo_social": [
        "trabajo social","trabajadora social","trabajador social","t.s.",
        "informe social","visita domiciliaria","red vincular","recurso social",
        "situacion social","situación social"
    ],
    "acompanante_terapeutico": [
        "acompañante terapeutico","acompañante terapéutico","acomp. terapeutico",
        "acomp.terapeutico","a.t.","tarea de at","rol del at","actividad con at",
        "acompañamiento terapeutico","acompañamiento terapéutico"
    ],
    "enfermeria": [
        "nota de enfermeria","nota de enfermería","control de signos vitales",
        "signos vitales","tension arterial","saturacion","medicada","medicado",
        "via oral","v.o.","guardia de enfermeria","turno de enfermeria"
    ],
    "psicopedagogia": [
        "psicopedagogia","psicopedagogía","psicopedagoga","evaluacion psicopedagogica"
    ]
}

MODELO_A_AREA = {
    "Enfermería": "enfermeria",
    "Psicología": "psicologia",
    "Psiquiatría": "psiquiatria",
    "Trabajo Social": "trabajo_social",
    "Otros": "otros"
}

def clasificar_area_hibrido(texto, nombre_profesional=None, modelo_nlp=None):
    """
    Clasificador híbrido con 4 capas:
    1. Diccionario profesional (firma)
    2. Reglas por texto/encabezado
    3. Modelo NLP
    4. Fallback otros
    Devuelve: (area, regla_disparada)
    """
    t = texto.lower()

    # CAPA 1: diccionario por nombre de profesional
    if nombre_profesional:
        area = detectar_area_por_profesional(nombre_profesional)
        if area:
            return area, f"diccionario_profesional:{nombre_profesional}"

    # CAPA 2: reglas por texto
    for area, keywords in REGLAS_AREA_TEXTO.items():
        for kw in keywords:
            if kw in t:
                return area, f"regla_texto:{kw}"

    # CAPA 3: modelo NLP
    if modelo_nlp is not None:
        try:
            pred = modelo_nlp.predict([texto])[0]
            area_mapped = MODELO_A_AREA.get(pred, "otros")
            return area_mapped, f"modelo_nlp:{pred}"
        except:
            pass

    return "otros", "fallback"

REGLAS_IC = {
    "interconsulta_pendiente": ["pendiente i/c","pendiente ic","pendiente interc","pendiente interconsulta","i/c pendiente","ic pendiente"],
    "interconsulta_inicial": ["se solicita interconsulta","interconsulta a ","requiere valoracion por","requiere valoración por","solicita ic","pide interconsulta","se pide ic"],
    "interconsulta_efectiva": ["evaluado por","valorado por","responde interconsulta","se responde interconsulta","se presenta servicio","fue evaluado","fue valorado","se realiza interconsulta","ic realizada","se realiza consulta","consulta nutricional","consulta por","interc.infecto","interc.nutri","interc."],
    "seguimiento": ["continua seguimiento","continúa seguimiento","revalua","reevalúa","seguimiento por","control por","nueva consulta por","segundo control"]
}

def clasificar_estado_ic(texto):
    t = texto.lower()
    SCORES = {"interconsulta_efectiva": 5, "interconsulta_inicial": 4, "interconsulta_pendiente": 3, "seguimiento": 2}
    for estado, frases in REGLAS_IC.items():
        if any(f in t for f in frases):
            return estado, SCORES.get(estado, 1)
    return "mencion_servicio", 0

def detectar_ics(registros):
    result = []
    for r in registros:
        t = r["texto"].lower()
        found = list(set([s for s in SERVICIOS_EXTERNOS if s in t]))
        if not found:
            continue
        if len(found) >= 2:
            # estado global del bloque (captura "se realiza interconsulta con X y Y")
            estado_global, score_global = clasificar_estado_ic(r["texto"])
            for servicio in found:
                # ventana local para detectar si ESE servicio tiene estado propio
                idx = t.find(servicio)
                ventana = t[max(0, idx-120):idx+120]
                estado_local, score_local = clasificar_estado_ic(ventana)
                # si la ventana local no aporta nada, usar estado global
                if estado_local == "mencion_servicio" and estado_global != "mencion_servicio":
                    estado_final, score_final = estado_global, score_global
                else:
                    estado_final, score_final = estado_local, score_local
                contar = estado_final in ["interconsulta_efectiva", "seguimiento"]
                result.append({"servicios": [servicio], "estado_interconsulta": estado_final, "score": score_final, "contar": contar, "evidencia": r["texto"][:100], "texto": r["texto"][:200], "multi_evento": True})
        else:
            estado, score = clasificar_estado_ic(r["texto"])
            contar = estado in ["interconsulta_efectiva", "seguimiento"]
            result.append({"servicios": found, "estado_interconsulta": estado, "score": score, "contar": contar, "evidencia": r["texto"][:100], "texto": r["texto"][:200], "multi_evento": False})
    return result

from pipeline.internaciones.modulo_internaciones import (
    procesar_mes as _procesar_mes_int,
    indicadores_periodo as _indicadores_periodo_int,
    episodios_periodo as _episodios_periodo_int,
    reingresos_periodo as _reingresos_periodo_int,
    historico_por_hc as _historico_por_hc_int,
)


@app.post("/internaciones/procesar")
async def internaciones_procesar(payload: dict):
    directorio = payload.get("directorio", "")
    periodo    = payload.get("periodo", "")
    if not directorio or not periodo:
        raise HTTPException(status_code=400, detail="Se requieren 'directorio' y 'periodo'")
    try:
        resultado = _procesar_mes_int(directorio, periodo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return resultado


@app.get("/internaciones/indicadores/{periodo}")
def internaciones_indicadores(periodo: str):
    datos = _indicadores_periodo_int(periodo)
    if datos is None:
        raise HTTPException(status_code=404, detail=f"No hay indicadores para el período {periodo}")
    return sanitize_public_payload(datos)


@app.get("/internaciones/episodios/{periodo}")
def internaciones_episodios(periodo: str):
    return sanitize_public_payload(_episodios_periodo_int(periodo))


@app.get("/internaciones/reingresos/{periodo}")
def internaciones_reingresos(periodo: str):
    return sanitize_public_payload(_reingresos_periodo_int(periodo))


@app.get("/internaciones/historico/{codigo_hc}")
def internaciones_historico(codigo_hc: str):
    return sanitize_public_payload(_historico_por_hc_int(codigo_hc))


# ── Censo upload (móvil / FastAPI directo) ────────────────────────────────────

import tempfile as _tempfile
from pipeline.censo.modulo_censo_mensual import (
    leer_archivo_censo as _leer_archivo_censo,
    filtrar_salud_mental as _filtrar_sm,
    stats_servicio_sm as _stats_servicio_sm,
)

_CENSO_ALLOWED_EXTS  = {".pdf", ".csv", ".xls", ".xlsx", ".html", ".htm"}
_CENSO_MAX_BYTES     = 200 * 1024 * 1024   # 200 MB
_CENSO_PRIV_COLS     = {"paciente", "documento", "nombre", "dni"}   # never returned


def _validar_censo_fastapi(filename: str, content_type: str, data: bytes):
    """Returns (ext: str, errores: list[str])."""
    ext  = pathlib.Path(filename).suffix.lower() if filename else ""
    head = (data or b"")[:16].lstrip()
    ct   = (content_type or "").lower()

    if ext not in _CENSO_ALLOWED_EXTS:
        if head.startswith(b"%PDF"):
            ext = ".pdf"
        elif head.startswith(b"PK"):
            ext = ".xlsx"
        elif head.startswith(b"\xd0\xcf\x11\xe0"):
            ext = ".xls"
        elif head.lower().startswith((b"<!doctype html", b"<html", b"<table")):
            ext = ".html"
        elif ct in ("text/csv", "text/plain"):
            ext = ".csv"
        elif ct == "application/pdf":
            ext = ".pdf"
        elif ct in ("text/html", "application/xhtml+xml"):
            ext = ".html"
        elif ct == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            ext = ".xlsx"
        elif ct == "application/vnd.ms-excel":
            ext = ".xls"

    errores: list[str] = []

    if ext not in _CENSO_ALLOWED_EXTS:
        errores.append(
            f"Formato no compatible: '{ext or '(sin extensión)'}'. "
            "Se aceptan PDF, CSV, XLS, XLSX, HTML, HTM."
        )
    if not data:
        errores.append("El archivo está vacío.")
    elif len(data) > _CENSO_MAX_BYTES:
        errores.append(
            f"El archivo supera el límite: {len(data)/(1024*1024):.1f} MB (máx 200 MB)."
        )
    if ext == ".pdf" and data and not data.startswith(b"%PDF"):
        errores.append("El archivo tiene extensión .pdf pero no contiene encabezado PDF válido (%PDF).")

    return ext, errores


@app.post("/censos/upload")
async def censos_upload(archivo: UploadFile = File(...)):
    data     = await archivo.read()
    filename = archivo.filename or ""
    ct       = archivo.content_type or ""

    ext, errores = _validar_censo_fastapi(filename, ct, data)
    if errores:
        raise HTTPException(status_code=400, detail=" | ".join(errores))

    ts          = dt_module.datetime.now(AR_TZ).strftime("%Y%m%d_%H%M%S")
    safe_name   = f"censo_{ts}{ext}"

    try:
        with _tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = pathlib.Path(tmp.name)

        try:
            df = _leer_archivo_censo(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        cols_all = list(df.columns)
        cols_pub = [c for c in cols_all
                    if c.lower() not in _CENSO_PRIV_COLS]

        filas_sm = None
        try:
            df_sm  = _filtrar_sm(df)
            stats  = _stats_servicio_sm(df)
            filas_sm = len(df_sm)
            if not df_sm.empty:
                df_sm = df_sm.copy()
                df_sm["_archivo"] = safe_name
                save_cols = [c for c in df_sm.columns if c.lower() not in _CENSO_PRIV_COLS]
                payload = {
                    "timestamp":        ts,
                    "filename_publico": safe_name,
                    "filas_detectadas": len(df),
                    "filas_sm":         filas_sm,
                    "stats":            stats,
                    "data":             df_sm[save_cols].to_dict(orient="records"),
                }
                (_MOBILE_UPLOAD_DIR / f"censo_{ts}.json").write_text(
                    json.dumps(payload, default=str, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            pass

        return {
            "ok":                True,
            "filename_publico":  safe_name,
            "filas_detectadas":  len(df),
            "filas_salud_mental": filas_sm,
            "columnas_detectadas": cols_pub,
            "error":             None,
        }

    except Exception as exc:
        return {
            "ok":                False,
            "filename_publico":  safe_name,
            "filas_detectadas":  None,
            "filas_salud_mental": None,
            "columnas_detectadas": None,
            "error":             str(exc),
        }


@app.get("/mobile", response_class=HTMLResponse)
async def mobile_upload_page():
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Subir Censo — HCD IA</title>
<style>
  *{box-sizing:border-box}
  body{font-family:sans-serif;margin:0;padding:20px;background:#0e1117;color:#fafafa;max-width:520px}
  h2{font-size:18px;margin-bottom:6px}
  p{font-size:13px;color:#aaa;margin:0 0 16px}
  label{display:block;margin-bottom:6px;font-size:14px}
  input[type=file]{display:block;width:100%;padding:12px;background:#1e2130;
    border:2px dashed #555;border-radius:8px;color:#fafafa;font-size:14px;margin-bottom:14px}
  button{width:100%;padding:14px;background:#ff4b4b;color:#fff;border:none;
    border-radius:8px;font-size:16px;font-weight:bold;cursor:pointer}
  button:disabled{background:#444;cursor:not-allowed}
  #dbg{margin-top:12px;padding:10px;background:#1a1a2a;border:1px solid #333;
    border-radius:6px;font-size:12px;font-family:monospace;color:#9fb;
    white-space:pre-wrap;display:none}
  #out{margin-top:10px;padding:14px;border-radius:8px;font-size:14px;
    white-space:pre-wrap;display:none;line-height:1.5}
  .ok{background:#1a3a1a;border:1px solid #2d6a2d;color:#6fcf6f;display:block!important}
  .err{background:#3a1a1a;border:1px solid #6a2d2d;color:#cf6f6f;display:block!important}
  .wait{background:#1a2a3a;border:1px solid #2d4a6a;color:#6f9fcf;display:block!important}
  .dbg{display:block!important}
</style>
</head>
<body>
<h2>Subir Censo VADIGU</h2>
<p>Seleccioná el archivo exportado de VADIGU (XLS, XLSX, CSV, HTML, PDF).</p>
<label>Archivo:</label>
<input type="file" id="f" accept=".xls,.xlsx,.csv,.html,.htm,.pdf"
  onchange="onFile()">
<button type="button" id="btn" onclick="upload()">Subir al servidor</button>
<div id="dbg"></div>
<div id="out"></div>
<script>
function onFile() {
  const fi = document.getElementById("f");
  if (!fi.files.length) return;
  const f = fi.files[0];
  const url = window.location.origin + "/censos/upload";
  dbg("Archivo: " + f.name
    + "\\nTamaño: " + f.size + " bytes"
    + "\\nTipo MIME: " + (f.type || "(sin tipo)")
    + "\\nURL destino: " + url);
}
async function upload() {
  const fi = document.getElementById("f");
  if (!fi.files.length) { show("Seleccioná un archivo primero.", "err"); return; }
  const f = fi.files[0];
  const url = window.location.origin + "/censos/upload";
  dbg("Archivo: " + f.name
    + "\\nTamaño: " + f.size + " bytes"
    + "\\nTipo MIME: " + (f.type || "(sin tipo)")
    + "\\nURL destino: " + url
    + "\\nEnviando…");
  const btn = document.getElementById("btn");
  btn.disabled = true;
  show("Subiendo…", "wait");
  try {
    const fd = new FormData();
    fd.append("archivo", f);
    const r = await fetch(url, {method: "POST", body: fd});
    const text = await r.text();
    dbg("Archivo: " + f.name
      + "\\nTamaño: " + f.size + " bytes"
      + "\\nTipo MIME: " + (f.type || "(sin tipo)")
      + "\\nURL destino: " + url
      + "\\nHTTP status: " + r.status
      + "\\nRespuesta: " + text.slice(0, 300));
    let j;
    try { j = JSON.parse(text); } catch(_) { j = null; }
    if (r.ok && j && j.ok) {
      const sm = j.filas_salud_mental != null
        ? "\\nFilas Salud Mental: " + j.filas_salud_mental : "";
      show("✓ Archivo recibido\\nTotal filas: " + j.filas_detectadas + sm
        + "\\n\\nYa podés ver los datos en el sistema.", "ok");
    } else {
      const detail = (j && (j.detail || j.error)) || text.slice(0, 200) || "error desconocido";
      show("✗ HTTP " + r.status + ": " + detail, "err");
    }
  } catch(e) {
    const msg = e.message + (e.stack ? "\\n" + e.stack.split("\\n").slice(0,3).join("\\n") : "");
    dbg("Archivo: " + f.name
      + "\\nTamaño: " + f.size + " bytes"
      + "\\nTipo MIME: " + (f.type || "(sin tipo)")
      + "\\nURL destino: " + url
      + "\\nERROR JS: " + msg);
    show("✗ Error: " + e.message, "err");
  }
  btn.disabled = false;
}
function dbg(msg) {
  const el = document.getElementById("dbg");
  el.textContent = msg; el.className = "dbg";
}
function show(msg, cls) {
  const el = document.getElementById("out");
  el.textContent = msg; el.className = cls;
}
</script>
</body>
</html>"""


@app.post("/hcd/procesar-modelo")
async def procesar_con_modelo(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    soup = BeautifulSoup(contenido, "html.parser")
    texto = soup.get_text(separator="\n", strip=True)
    # Extraer metricas del cronologico
    import re as re2
    fechas = re2.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    # VADIGU inserta en el header las 2 primeras fechas como rango del reporte
    # (siempre 6 meses = 181 días). Se saltean para usar fechas clínicas reales.
    fechas_clinicas = fechas[2:] if len(fechas) > 2 else fechas
    if fechas_clinicas:
        import datetime as dt_module
        try:
            fechas_dt = [dt_module.datetime.strptime(f, "%d/%m/%Y") for f in fechas_clinicas]
            fecha_ini = min(fechas_dt)
            fecha_fin = max(fechas_dt)
            dias_internacion = (fecha_fin - fecha_ini).days
        except:
            dias_internacion = 0
    else:
        dias_internacion = 0
    reingresos = texto.lower().count("internación - hospital") + texto.lower().count("internacion - hospital")
    cambios_cama = texto.lower().count("pase de cama")
    pac_codigo = _re.sub(r'[^A-Za-z0-9]', '', archivo.filename)[:10].upper() or "PAC"
    registros = parsear_intervenciones(texto, pac_codigo)
    if not registros:
        return {"error": "Sin intervenciones", "archivo": _archivo_publico(archivo.filename)}
    modelo = joblib.load("modelo_area_intervenciones.pkl")
    areas_detalle = []
    for r in registros:
        m = _re.search(r'Profesional:\s*([A-ZÁÉÍÓÚÑ][^\n]+)', r["texto"])
        nombre_prof = m.group(1).strip() if m else None
        area, regla = clasificar_area_hibrido(r["texto"], nombre_prof, modelo)
        r["id_intervencion"] = generar_id_intervencion(pac_codigo, r["fecha"], r["hora"], area, r["tipo"], r["texto"])
        areas_detalle.append({"area": area, "regla": pseudonimizar_texto(regla), "texto": pseudonimizar_texto(r["texto"][:80]),
                              "id": r["id_intervencion"], "cuenta": r["criterio_conteo"]["cuenta"]})
    conteo = dict(Counter([a["area"] for a in areas_detalle if a["cuenta"]]))
    variables_dict = {
        "ideacion_autolitica": ["ideacion","ideas de muerte","ideas suicidas","autolesion","intento de suicidio","autolisis"],
        "alucinaciones": ["alucinac","voces","escucha voces"],
        "delirio_psicosis": ["delirio","delirante","psicosis","psicotico","f20","esquizofren"],
        "agresividad": ["agresiv","violencia","heteroagresiv","hostil"],
        "ansiedad_insomnio": ["ansiedad","insomnio","angustia","agitac","impulsiv"],
        "vulnerabilidad_social": ["vulnerabilidad social","sin recursos","situacion social"],
        "sin_red_vincular": ["sin red vincular","sin referente vincular","sin familia","sin apoyo"],
        "adherencia_problematica": ["no adhiere","abandono","discontinua medicacion","negativ"],
        "internacion_prolongada": ["internado hace","dias de internacion","internacion prolongada"],
        "consumo_sustancias": ["consumo","alcohol","droga","adiccion","sustancia"],
        "ideas_persecutorias": ["persecutori","perseguido","lo persiguen"],
        "estado_estable": ["tranquil","estable","compensad"],
        "bradipsiquia": ["bradipsiquic","enlentecido","lentitud"],
        "sin_criterio_internacion": ["no presenta criterio para continuar internado","ya no requiere internacion"],
        "riesgo_fuga": ["fuga","se fue sin alta","abandono el servicio"],
        "crisis": ["crisis","descompensa","reagudiza"]
    }
    texto_lower = texto.lower()
    variables_clinicas = {}
    for var, palabras in variables_dict.items():
        variables_clinicas[var] = any(p in texto_lower for p in palabras)
    # Detectar interconsultas por nombre de profesional
    import re as re3
    patron_prof = r'Profesional:\s*([A-ZÁÉÍÓÚÑ][^\n]+?)(?:\s*-\s*([A-ZÁÉÍÓÚÑ][^\n]+?))?(?:\s*Matrícula|\s*\d|$)'
    ics_prof = []
    for match in re3.finditer(patron_prof, texto):
        nombre = match.group(1).strip()
        especialidad = match.group(2).strip() if match.group(2) else ""
        area_sm = detectar_area_por_profesional(nombre)
        especialidad_lower = especialidad.lower()
        es_sm = any(s in especialidad_lower for s in ["psicolog","psiquiat","enfermer","trabajo social","terapia ocup","acompañante","salud mental","guardia de piso"])
        if area_sm is None and especialidad and not es_sm:
            # Es externo con especialidad declarada
            ics_prof.append({
                "profesional": "[PROFESIONAL_ELIMINADO]",
                "especialidad": especialidad,
                "estado": "detectada"
            })
    ics = detectar_ics(registros)
    # Combinar interconsultas por texto y por profesional
    for ic_p in ics_prof:
        if not any(ic_p["especialidad"].lower() in str(ic).lower() for ic in ics):
            estado_p, score_p = clasificar_estado_ic(ic_p.get("contexto",""))
            ics.append({
                "servicios": [ic_p["especialidad"].lower()],
                "estado_interconsulta": estado_p,
                "score": score_p,
                "contar": True,
                "evidencia": f"Profesional externo - {ic_p['especialidad']}",
                "texto": f"Profesional externo - {ic_p['especialidad']}"
            })
    total_contadas = sum(1 for r in registros if r.get("criterio_conteo", {}).get("cuenta", False))
    ics_publicas = sanitize_public_payload(ics[:10])
    resumen = {"archivo": _archivo_publico(archivo.filename), "total_intervenciones": total_contadas, "total_registros_raw": len(registros), "intervenciones_por_tipo": dict(Counter([next((m for m in ["nota de enfermería","evolución clínica","seguimiento","diagnóstico","indicación","motivo de consulta"] if m in r["tipo"].lower().replace("enfermeria","enfermería").replace("evolucion","evolución").replace("diagnostico","diagnóstico").replace("indicacion","indicación").replace("clinica","clínica")), "otros") for r in registros if r.get("criterio_conteo", {}).get("cuenta", False)])), "internacion": {"dias_totales": dias_internacion, "reingresos": max(0, reingresos-1), "cambios_cama": cambios_cama}, "modelo_nlp": {"modelo": "TF-IDF + Logistic Regression", "accuracy": 0.9298}, "intervenciones_por_area": conteo, "detalle_clasificacion": areas_detalle[:30], "variables_clinicas_detectadas": variables_clinicas, "interconsultas_detectadas": ics_publicas}
    resumen = sanitize_public_payload(resumen)
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
        (archivo.filename, json.dumps(resumen, ensure_ascii=False), pseudonimizar_texto(texto[:500]), datetime.datetime.now().isoformat()))
    con.commit(); con.close()
    return resumen
