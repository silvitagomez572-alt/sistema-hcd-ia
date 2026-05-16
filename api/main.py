import json
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from zoneinfo import ZoneInfo

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
BASE_DIR = pathlib.Path(__file__).resolve().parent
HCD_PATH = BASE_DIR / "hcd" / "data" / "json_maestro_hc_salud_mental.json"

app = FastAPI(title="Sistema HCD IA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {
        "modelo_nlp": data["modelo_nlp"],
        "carga_asistencial": data["carga_asistencial"],
        "intervenciones_por_area": data["intervenciones_por_area"],
        "internacion": data["internacion"],
        "variables_clinicas_detectadas": data["variables_clinicas_detectadas"],
        "estrategia_externacion": data["estrategia_externacion"]
    }
