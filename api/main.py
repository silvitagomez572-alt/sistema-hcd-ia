import json
import pathlib
import io
import httpx
import chromadb
import pypdf
from chromadb.utils import embedding_functions
from fastapi import FastAPI, UploadFile, File, HTTPException
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
        return {"archivo": archivo.filename, "resumen": resumen}

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
    return [{"id": r[0], "archivo": r[1], "resumen": r[2], "fecha": r[3],
             "codigo_paciente": f"PAC-{r[0]:03d}"} for r in rows]

@app.get("/hcd/reporte-total")
def reporte_total():
    con = sqlite3.connect(DB_PATH)
    # Deduplicar: mantener el registro más reciente por archivo
    rows = con.execute(
        "SELECT id, archivo, resumen, fecha FROM hcs_procesadas "
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
        codigo = f"PAC-{r[0]:03d}"
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
            "archivo": r[1],
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
    return {
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
    }

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
    ],
    "psicologia": [
        "psicologia","psicología","psicologa","psicólogo","psicóloga",
        "espacio psicologico","espacio psicológico","intervencion psicologica",
        "intervencion psicológica","entrevista psicológica","entrevista psicologica",
        "abordaje psicológico","abordaje psicologico",
    ],
    "terapia_ocupacional": [
        "terapia ocupacional","terapista ocupacional","t.o.","to ","terapeuta ocupacional",
        "taller de to","actividad de to","espacio de to","taller ocupacional",
        "actividades de la vida diaria","avd","actividades ocupacionales"
    ],
    "trabajo_social": [
        "trabajo social","trabajadora social","trabajador social","ts ","t.s.",
        "informe social","visita domiciliaria","red vincular","recurso social",
        "situacion social","situación social"
    ],
    "acompanante_terapeutico": [
        "acompañante terapeutico","acompañante terapéutico","acomp. terapeutico",
        "acomp.terapeutico","at ","a.t.","tarea de at","rol del at","actividad con at",
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
        return {"error": "Sin intervenciones", "archivo": archivo.filename}
    modelo = joblib.load("modelo_area_intervenciones.pkl")
    areas_detalle = []
    for r in registros:
        m = _re.search(r'Profesional:\s*([A-ZÁÉÍÓÚÑ][^\n]+)', r["texto"])
        nombre_prof = m.group(1).strip() if m else None
        area, regla = clasificar_area_hibrido(r["texto"], nombre_prof, modelo)
        r["id_intervencion"] = generar_id_intervencion(pac_codigo, r["fecha"], r["hora"], area, r["tipo"], r["texto"])
        areas_detalle.append({"area": area, "regla": regla, "texto": r["texto"][:80],
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
    total_contadas = sum(1 for r in registros if r.get("criterio_conteo", {}).get("cuenta", False))
    resumen = {"archivo": archivo.filename, "total_intervenciones": total_contadas, "total_registros_raw": len(registros), "intervenciones_por_tipo": dict(Counter([next((m for m in ["nota de enfermería","evolución clínica","seguimiento","diagnóstico","indicación","motivo de consulta"] if m in r["tipo"].lower().replace("enfermeria","enfermería").replace("evolucion","evolución").replace("diagnostico","diagnóstico").replace("indicacion","indicación").replace("clinica","clínica")), "otros") for r in registros if r.get("criterio_conteo", {}).get("cuenta", False)])), "internacion": {"dias_totales": dias_internacion, "reingresos": max(0, reingresos-1), "cambios_cama": cambios_cama}, "modelo_nlp": {"modelo": "TF-IDF + Logistic Regression", "accuracy": 0.9298}, "intervenciones_por_area": conteo, "detalle_clasificacion": areas_detalle[:30], "variables_clinicas_detectadas": variables_clinicas, "interconsultas_detectadas": ics[:10]}
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO hcs_procesadas (archivo, resumen, texto_extraido, fecha) VALUES (?,?,?,?)",
        (archivo.filename, json.dumps(resumen, ensure_ascii=False), texto[:500], datetime.datetime.now().isoformat()))
    con.commit(); con.close()
    return resumen

