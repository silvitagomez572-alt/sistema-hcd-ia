import json
import pathlib
import httpx
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import datetime as dt_module
from zoneinfo import ZoneInfo

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
BASE_DIR = pathlib.Path(__file__).resolve().parent
HCD_PATH = BASE_DIR / "hcd" / "data" / "json_maestro_hc_salud_mental.json"

app = FastAPI(title="Sistema HCD IA", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def load_hcd():
    with open(HCD_PATH, encoding="utf-8") as f:
        return json.load(f)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(AR_TZ).isoformat()}

@app.get("/hcd/summary")
def hcd_summary():
    return load_hcd()

@app.get("/hcd/interconsultas")
def hcd_interconsultas():
    return load_hcd()["interconsultas_detectadas"]

@app.get("/hcd/metricas")
def hcd_metricas():
    data = load_hcd()
    return {"modelo_nlp": data["modelo_nlp"], "carga_asistencial": data["carga_asistencial"], "intervenciones_por_area": data["intervenciones_por_area"], "internacion": data["internacion"], "variables_clinicas_detectadas": data["variables_clinicas_detectadas"], "estrategia_externacion": data["estrategia_externacion"]}

@app.post("/llm/consultar")
async def llm_consultar(payload: dict):
    pregunta = payload.get("pregunta", "")
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post("http://localhost:11434/api/generate", json={"model": "gemma:2b", "prompt": f"Eres un asistente clinico hospitalario. Responde en espanol. {pregunta}", "stream": False})
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
        r = await client.post("http://localhost:11434/api/generate", json={"model": "gemma:2b", "prompt": prompt, "stream": False})
        data = r.json()
        return {"respuesta": data.get("response", ""), "fuentes": resultados["metadatas"][0]}

from fastapi import UploadFile, File
from bs4 import BeautifulSoup
import xlrd, openpyxl, io

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
    prompt = f"""Eres un asistente clinico hospitalario. Analiza esta historia clinica y extrae en espanol:
1. Datos del paciente (nombre si aparece, edad, servicio)
2. Principales intervenciones detectadas
3. Areas involucradas
4. Variables clinicas relevantes
Historia clinica: {texto}
Responde de forma estructurada y breve."""
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post("http://localhost:11434/api/generate", json={"model": "gemma:2b", "prompt": prompt, "stream": False})
        data = r.json()
        resumen = data.get("response", "")
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
            (archivo.filename, resumen, texto[:500], datetime.datetime.now().isoformat()))
        con.commit()
        con.close()
        return {"archivo": archivo.filename, "resumen": resumen, "texto_extraido": texto[:500]}

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
    con.commit()
    con.close()

init_db()

@app.get("/hcd/reportes")
def get_reportes():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, archivo, resumen, fecha FROM hcs_procesadas ORDER BY fecha DESC").fetchall()
    con.close()
    return [{"id": r[0], "archivo": r[1], "resumen": r[2], "fecha": r[3]} for r in rows]


import joblib
import re as _re
from collections import Counter

_modelo_nlp = None

def get_modelo():
    global _modelo_nlp
    if _modelo_nlp is None:
        _modelo_nlp = joblib.load("modelo_area_intervenciones.pkl")
    return _modelo_nlp

def parsear_intervenciones(texto):
    import re
    patron = r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}:\d{2})\s*hs'
    marcadores = ["nota de enfermeria","nota de enfermería","evolucion clinica","evolución clínica","seguimiento","diagnostico","diagnóstico","indicacion","indicación","motivo de consulta"]
    registros = []
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
                registros.append({"fecha": fb, "hora": hb, "tipo": tipo, "texto": bloque.strip()})
            bloque = linea; tipo = linea; fb = fecha_actual; hb = hora_actual
        else:
            if bloque: bloque += " " + linea
    if bloque:
        registros.append({"fecha": fb, "hora": hb, "tipo": tipo, "texto": bloque.strip()})
    return registros

SERVICIOS_SALUD_MENTAL = ["psicologia","psicología","psiquiatria","psiquiatría","enfermeria","enfermería","trabajo social","terapia ocupacional","acompañante terapeutico","acompañante terapéutico","salud mental"]
SERVICIOS_EXTERNOS = ["cardiologia","cardiología","cirugia","cirugía","cirugia general","cirugía general","cirugia oncologica","cirugia vascular","cirugía vascular","clinica medica","clínica médica","dermatologia","dermatología","endocrinologia","endocrinología","fonoaudiologia","fonoaudiología","gastroenterologia","gastroenterología","ginecologia","ginecología","hematologia","hematología","infectologia","infectología","kinesiologia","kinesiología","nefrologia","nefrología","neurologia","neurología","nutricion","nutrición","oftalmologia","oftalmología","oncologia","oncología","otorrinolaringologia","traumatologia","traumatología","urologia","urología","uco","odontologia","odontología"]

def detectar_ics(registros):
    result = []
    for r in registros:
        t = r["texto"].lower()
        found = list(set([s for s in SERVICIOS_EXTERNOS if s in t]))
        if found:
            if any(p in t for p in ["ausente","no concurre","no asistio"]):
                estado = "ausente"
            elif any(p in t for p in ["reeval","seguimiento","control por","continua"]):
                estado = "seguimiento"
            elif any(p in t for p in ["se realiz","se indica","se solicita","interconsulta","evaluad"]):
                estado = "resuelta"
            else:
                estado = "detectada"
            result.append({"servicios": found, "estado": estado, "motivo": r["texto"][:100], "texto": r["texto"][:200]})
    return result

@app.post("/hcd/procesar-modelo")
async def procesar_con_modelo(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    soup = BeautifulSoup(contenido, "html.parser")
    texto = soup.get_text(separator="\n", strip=True)
    # Extraer metricas del cronologico
    import re as re2
    fechas = re2.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if fechas:
        import datetime as dt_module
        try:
            fecha_ini = dt_module.datetime.strptime(fechas[0], "%d/%m/%Y")
            fecha_fin = dt_module.datetime.strptime(fechas[-1], "%d/%m/%Y")
            dias_internacion = (fecha_fin - fecha_ini).days
        except:
            dias_internacion = 0
    else:
        dias_internacion = 0
    reingresos = texto.lower().count("internación - hospital") + texto.lower().count("internacion - hospital")
    cambios_cama = texto.lower().count("pase de cama")
    registros = parsear_intervenciones(texto)
    if not registros:
        return {"error": "Sin intervenciones", "archivo": archivo.filename}
    modelo = joblib.load("modelo_area_intervenciones.pkl")
    textos = [r["texto"] for r in registros]
    areas = modelo.predict(textos)
    conteo = dict(Counter(areas))
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
    ics = detectar_ics(registros)
    resumen = {"archivo": archivo.filename, "total_intervenciones": len(registros), "internacion": {"dias_totales": dias_internacion, "reingresos": max(0, reingresos-1), "cambios_cama": cambios_cama}, "modelo_nlp": {"modelo": "TF-IDF + Logistic Regression", "accuracy": 0.9298}, "intervenciones_por_area": conteo, "variables_clinicas_detectadas": variables_clinicas, "interconsultas_detectadas": ics[:10]}
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
        (archivo.filename, json.dumps(resumen, ensure_ascii=False), texto[:500], datetime.datetime.now().isoformat()))
    con.commit(); con.close()

