import json
import pathlib
import httpx
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
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

SERVICIOS_EXTERNOS = ["infectologia","infectología","clinica medica","clínica médica","neurologia","neurología","traumatologia","traumatología","nutricion","nutrición","ginecologia","ginecología","psiquiatria","psiquiatría","odontologia","odontología","oftalmologia","oftalmología","cardiologia","cardiología","kinesiologia","kinesiología","fonoaudiologia","fonoaudiología","endocrinologia","endocrinología","urologia","urología","hematologia","hematología","gastroenterologia","gastroenterología","dermatologia","dermatología","reumatologia","reumatología","nefrologia","nefrología","oncologia","oncología","otorrinolaringologia","cirugia vascular","cirugia general","trabajo social","terapia ocupacional"]

def detectar_ics(registros):
    svcs = ["infectologia","infectología","clinica medica","clínica médica","neurologia","neurología","traumatologia","traumatología","nutricion","nutrición","ginecologia","ginecología","psiquiatria","psiquiatría","odontologia","odontología","oftalmologia","oftalmología","cardiologia","cardiología","kinesiologia","kinesiología","fonoaudiologia","fonoaudiología","endocrinologia","endocrinología","urologia","urología","hematologia","hematología","gastroenterologia","gastroenterología","dermatologia","dermatología","reumatologia","reumatología","nefrologia","nefrología","oncologia","oncología","otorrinolaringologia","cirugia vascular","cirugía vascular","cirugia general","cirugía general","salud mental","trabajo social","psicologia","psicología","terapia ocupacional"]
    result = []
    for r in registros:
        t = r["texto"].lower()
        found = list(set([s for s in svcs if s in t]))
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
    registros = parsear_intervenciones(texto)
    if not registros:
        return {"error": "Sin intervenciones", "archivo": archivo.filename}
    modelo = joblib.load("modelo_area_intervenciones.pkl")
    textos = [r["texto"] for r in registros]
    areas = modelo.predict(textos)
    conteo = dict(Counter(areas))
    ics = detectar_ics(registros)
    resumen = {"archivo": archivo.filename, "total_intervenciones": len(registros), "intervenciones_por_area": conteo, "interconsultas_detectadas": ics[:10]}
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
        (archivo.filename, json.dumps(resumen, ensure_ascii=False), texto[:500], datetime.datetime.now().isoformat()))
    con.commit(); con.close()
    return resumen
