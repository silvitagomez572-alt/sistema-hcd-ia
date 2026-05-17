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
    archivo = st.file_uploader("Archivo", type=["html","txt","pdf","png","jpg","xls","xlsx"])
    if archivo:
        st.success(f"Cargado: {archivo.name}")
        if st.button("Procesar"):
            with st.spinner("Procesando HC con IA..."):
                try:
                    files = {"archivo": (archivo.name, archivo.getvalue(), archivo.type)}
                    r = requests.post(f"{API}/hcd/procesar", files=files)
                    if r.status_code == 200:
                        data = r.json()
                        st.success("HC procesada correctamente")
                        st.markdown("### Resumen IA")
                        st.write(data["resumen"])
                        with st.expander("Texto extraido"):
                            st.write(data["texto_extraido"])
                    else:
                        st.error(f"Error: {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
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
    st.info("Modelo: gemma:2b via Ollama | Accuracy base: 92.98%")
    pregunta = st.text_input("Consulta al LLM", placeholder="Resume las intervenciones de salud mental")
    if st.button("Ejecutar"):
        if pregunta:
            with st.spinner("Consultando LLM..."):
                try:
                    r = requests.post(f"{API}/llm/consultar", json={"pregunta": pregunta})
                    if r.status_code == 200:
                        st.success(r.json()["respuesta"])
                    else:
                        st.error(f"Error API: {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Escribi una consulta primero.")
elif modulo == "Base de Conocimiento":
    st.title("RAG - Protocolos Clinicos")
    q = st.text_input("Consultar", placeholder="protocolo contencion salud mental")
    if st.button("Buscar"):
        if q:
            with st.spinner("Buscando en base de conocimiento..."):
                try:
                    r = requests.post(f"{API}/rag/consultar", json={"pregunta": q})
                    if r.status_code == 200:
                        st.success(r.json()["respuesta"])
                    else:
                        st.error(f"Error API: {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Escribi una consulta primero.")
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
    reps = requests.get(f"{API}/hcd/reportes")
    hcs = reps.json() if reps.status_code == 200 else []
    opciones = {f"{h['id']} - {h['archivo']}": h for h in hcs}
    seleccion = st.selectbox("Seleccionar HC", list(opciones.keys())) if opciones else None
    if seleccion:
        hc_sel = opciones[seleccion]
        try:
            data = json.loads(hc_sel["resumen"])
        except:
            st.info(hc_sel["resumen"])
            data = None
    else:
        data = None
    r = requests.get(f"{API}/hcd/metricas")
    if seleccion and data is None:
        st.warning("Esta HC fue procesada por IA - ver resumen arriba")
    elif r.status_code == 200 and (not seleccion or data):
        if not seleccion:
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
