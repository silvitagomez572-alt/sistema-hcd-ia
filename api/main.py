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
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

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

REGLAS_IC = {
    "interconsulta_inicial": ["se solicita interconsulta","interconsulta a ","requiere valoracion por","requiere valoración por","solicita ic","pide interconsulta","se pide ic","pendiente i/c","pendiente ic","pendiente interconsulta","i/c pendiente"],
    "interconsulta_efectiva": ["evaluado por","valorado por","responde interconsulta","se responde interconsulta","se presenta servicio","fue evaluado","fue valorado","se realiza interconsulta","ic realizada","se realiza consulta","consulta nutricional","consulta por","interc.infecto","interc.nutri","interc."],
    "seguimiento": ["continua seguimiento","continúa seguimiento","revalua","reevalúa","seguimiento por","control por","nueva consulta por","segundo control"]
}

def clasificar_estado_ic(texto):
    t = texto.lower()
    for estado, frases in REGLAS_IC.items():
        if any(f in t for f in frases):
            score = 5 if estado == "interconsulta_efectiva" else 4 if estado == "interconsulta_inicial" else 2
            return estado, score
    return "mencion_servicio", 0

def detectar_ics(registros):
    result = []
    for r in registros:
        t = r["texto"].lower()
        found = list(set([s for s in SERVICIOS_EXTERNOS if s in t]))
        if found:
            estado, score = clasificar_estado_ic(r["texto"])
            contar = estado != "mencion_servicio"
            result.append({"servicios": found, "estado_interconsulta": estado, "score": score, "contar": contar, "evidencia": r["texto"][:100], "texto": r["texto"][:200]})
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
                "profesional": nombre,
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
                "evidencia": f"Profesional externo: {ic_p['profesional']} - {ic_p['especialidad']}",
                "texto": f"Profesional externo: {ic_p['profesional']} - {ic_p['especialidad']}"
            })
    resumen = {"archivo": archivo.filename, "total_intervenciones": len(registros), "internacion": {"dias_totales": dias_internacion, "reingresos": max(0, reingresos-1), "cambios_cama": cambios_cama}, "modelo_nlp": {"modelo": "TF-IDF + Logistic Regression", "accuracy": 0.9298}, "intervenciones_por_area": conteo, "variables_clinicas_detectadas": variables_clinicas, "interconsultas_detectadas": ics[:10]}
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
        (archivo.filename, json.dumps(resumen, ensure_ascii=False), texto[:500], datetime.datetime.now().isoformat()))
    con.commit(); con.close()
    return resumen

