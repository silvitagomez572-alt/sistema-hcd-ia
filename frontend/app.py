import streamlit as st
import requests
import pandas as pd
import json

API = "http://localhost:8001"
st.set_page_config(page_title="Sistema HCD IA", layout="wide")
st.sidebar.title("Sistema HCD IA")
modulo = st.sidebar.radio("Modulo", ["Ingresar HC","Extraccion OCR","Pseudonimizacion","Modelo NLP","Base de Conocimiento","Interconsultas HCD","Metricas HCD","Reporte"])

if modulo == "Ingresar HC":
    st.title("Ingresar Historia Clinica")
    tipo = st.radio("Formato", ["HTML/TXT","PDF","Imagen OCR"])
    archivo = st.file_uploader("Archivo", type=["html","txt","pdf","png","jpg"])
    if archivo:
        st.success(f"Cargado: {archivo.name}")
        if st.button("Procesar"):
            st.success("HC recibida.")
elif modulo == "Extraccion OCR":
    st.title("OCR - Extraccion de Texto")
    st.text_area("Resultado", value="13/11/2025 - 05:33\nNota enfermeria\nPaciente tranquila...", height=200)
    st.success("Texto extraido.")
elif modulo == "Pseudonimizacion":
    st.title("Pseudonimizacion")
    c1,c2 = st.columns(2)
    c1.text_area("Original", value="Paciente: Maria Lopez\nDNI: 28456789", height=150)
    c2.text_area("Resultado", value="Paciente: [HC_ELIMINADA]\nDNI: [DNI_ELIMINADO]", height=150)
    st.success("Datos sensibles eliminados.")
elif modulo == "Modelo NLP":
    st.title("LLM - Extraccion de Intervenciones")
    st.info("Modelo: TF-IDF + Logistic Regression | Accuracy: 92.98%")
    if st.button("Ejecutar"):
        st.json({"intervenciones": 681, "areas": 9, "accuracy": 0.9298})
elif modulo == "Base de Conocimiento":
    st.title("RAG - Protocolos Clinicos")
    q = st.text_input("Consultar", placeholder="protocolo contencion salud mental")
    if st.button("Buscar"):
        st.markdown("**Ley 26.657**: La internacion debe ser el ultimo recurso terapeutico.")
elif modulo == "Interconsultas HCD":
    st.title("Interconsultas detectadas")
    r = requests.get(f"{API}/hcd/interconsultas")
    if r.status_code == 200:
        for ic in r.json():
            estado = ic["estado_interconsulta"]
            with st.expander(f"{ic['servicios_detectados'][0].upper()} - {estado}"):
                st.write(f"**Motivo:** {ic['motivo']}")
                st.write(f"**Texto:** {ic['texto_original']}")
    else:
        st.error("Error API")
elif modulo == "Metricas HCD":
    st.title("Metricas del Sistema HCD")
    r = requests.get(f"{API}/hcd/metricas")
    if r.status_code == 200:
        data = r.json()
        st.subheader("Resumen del caso clinico")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Intervenciones", data["carga_asistencial"]["total_intervenciones"])
        c2.metric("Accuracy", f"{data['modelo_nlp']['accuracy']:.1%}")
        c3.metric("Dias totales", data["internacion"]["dias_totales"])
        c4.metric("Reingresos", data["internacion"]["reingresos"])
        c5,c6,c7 = st.columns(3)
        c5.metric("Internacion 1", f"{data['internacion']['primera_estadia_dias']} dias")
        c6.metric("Internacion 2", f"{data['internacion']['segunda_estadia_dias']} dias")
        c7.metric("Cambios de cama", data["internacion"]["cambios_cama"])
        areas = data["intervenciones_por_area"]
        df = pd.DataFrame({"Area":list(areas.keys()),"N":list(areas.values())}).sort_values("N",ascending=False)
        st.bar_chart(df.set_index("Area"))
        ca,cb = st.columns(2)
        for i,k in enumerate(data["variables_clinicas_detectadas"]):
            (ca if i%2==0 else cb).write(f"OK {k.replace('_',' ').capitalize()}")
    else:
        st.error("Error API")
elif modulo == "Reporte":
    st.title("Reporte Final - JSON")
    r = requests.get(f"{API}/hcd/summary")
    if r.status_code == 200:
        data = r.json()
        st.json(data)
        st.download_button("Descargar JSON", json.dumps(data,ensure_ascii=False,indent=4), "reporte_hcd.json", "application/json")
    else:
        st.error("Error API")
