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
                    r = requests.post(f"{API}/hcd/procesar-modelo", files=files)
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

    ESTADO_COLOR = {
        "interconsulta_efectiva":  ("🟢", "success"),
        "seguimiento":             ("🟢", "success"),
        "interconsulta_inicial":   ("🔵", "info"),
        "interconsulta_pendiente": ("🟡", "warning"),
        "mencion_servicio":        ("⚪", "secondary"),
    }

    reps = requests.get(f"{API}/hcd/reportes")
    hcs_raw = reps.json() if reps.status_code == 200 else []

    # Deduplicar por archivo (mismo criterio que Métricas)
    seen = {}
    for h in hcs_raw:
        if h["archivo"] not in seen:
            seen[h["archivo"]] = h
    hcs = list(seen.values())

    if not hcs:
        st.warning("No hay HCs procesadas.")
        st.stop()

    opciones = {"— Todas las HCs —": None}
    opciones.update({f"{h['nombre_paciente'] or h['archivo']}": h for h in hcs})
    sel = st.selectbox("Seleccionar paciente", list(opciones.keys()))
    hcs_mostrar = hcs if opciones[sel] is None else [opciones[sel]]

    for h in hcs_mostrar:
        nombre = h.get("nombre_paciente") or h["archivo"]
        try:
            data = json.loads(h["resumen"])
        except:
            continue
        ics = data.get("interconsultas_detectadas", [])
        if not ics:
            continue

        st.markdown(f"### 👤 {nombre}")
        st.caption(f"Archivo: {h['archivo']} · {h['fecha'][:10]}")

        for ic in ics:
            svcs = ic.get("servicios", [])
            estado = ic.get("estado_interconsulta", "mencion_servicio")
            score = ic.get("score", 0)
            contar = ic.get("contar", False)
            evidencia = ic.get("evidencia", ic.get("texto", ""))
            emoji, color = ESTADO_COLOR.get(estado, ("⚪", "secondary"))
            svc_label = ", ".join(s.upper() for s in svcs) if svcs else "SERVICIO"
            contar_label = "✔ cuenta" if contar else "✘ no cuenta"

            if color == "success":
                st.success(f"{emoji} **{svc_label}** · {estado.replace('_',' ')} · score {score} · {contar_label}")
            elif color == "warning":
                st.warning(f"{emoji} **{svc_label}** · {estado.replace('_',' ')} · score {score} · {contar_label}")
            elif color == "info":
                st.info(f"{emoji} **{svc_label}** · {estado.replace('_',' ')} · score {score} · {contar_label}")
            else:
                st.markdown(f"{emoji} **{svc_label}** · {estado.replace('_',' ')} · score {score} · {contar_label}")
            if evidencia:
                st.caption(f"↳ {evidencia[:120]}")

        st.divider()
elif modulo == "Metricas HCD":
    st.title("Métricas del Sistema HCD")
    import altair as alt

    # Datos frescos desde SQLite via endpoint (no JSON maestro cacheado)
    reps = requests.get(f"{API}/hcd/reportes")
    hcs_raw = reps.json() if reps.status_code == 200 else []

    # Deduplicar en memoria: quedarse con el registro más reciente por archivo
    seen_arch = {}
    for h in hcs_raw:
        if h["archivo"] not in seen_arch:
            seen_arch[h["archivo"]] = h
    hcs = list(seen_arch.values())

    n_dups = len(hcs_raw) - len(hcs)
    if n_dups > 0:
        st.warning(f"{n_dups} registro(s) duplicado(s) detectado(s).")
        if st.button("Limpiar duplicados en BD"):
            r_del = requests.delete(f"{API}/hcd/reportes/duplicados")
            if r_del.status_code == 200:
                st.success(f"Eliminados: {r_del.json()['eliminados']}")
                st.rerun()

    if not hcs:
        st.warning("No hay HCs procesadas aún.")
        st.stop()

    # Selector de HC
    opciones = {"— Todas las HCs —": None}
    opciones.update({f"{h['nombre_paciente'] or h['archivo']}": h for h in hcs})
    seleccion = st.selectbox("Seleccionar HC", list(opciones.keys()))
    hc_sel = opciones[seleccion]

    # Construir datos: agregar todas o mostrar una sola
    ics_all = []
    if hc_sel is None:
        areas_total, total_int, reingresos, cambios, dias_list = {}, 0, 0, 0, []
        for h in hcs:
            try:
                d = json.loads(h["resumen"])
                for k, v in d.get("intervenciones_por_area", {}).items():
                    areas_total[k] = areas_total.get(k, 0) + v
                total_int += d.get("total_intervenciones", 0)
                intern = d.get("internacion", {})
                reingresos += intern.get("reingresos", 0)
                cambios += intern.get("cambios_cama", 0)
                if intern.get("dias_totales"):
                    dias_list.append(intern["dias_totales"])
                for ic in d.get("interconsultas_detectadas", []):
                    for svc in ic.get("servicios", []):
                        ics_all.append({"Paciente": h.get("nombre_paciente") or h["archivo"],
                            "Servicio": svc, "Estado": ic.get("estado_interconsulta", ""),
                            "Score": ic.get("score", 0), "Contar": ic.get("contar", False)})
            except:
                pass
        data = {"intervenciones_por_area": areas_total, "total_intervenciones": total_int,
                "internacion": {"dias_totales": round(sum(dias_list)/len(dias_list)) if dias_list else 0,
                                "reingresos": reingresos, "cambios_cama": cambios},
                "modelo_nlp": {"accuracy": 0.9298}}
        vars_clinicas = {}
    else:
        try:
            data = json.loads(hc_sel["resumen"])
        except:
            st.error("No se pudo leer el resumen de esta HC.")
            st.stop()
        vars_clinicas = data.get("variables_clinicas_detectadas", {})
        for ic in data.get("interconsultas_detectadas", []):
            for svc in ic.get("servicios", []):
                ics_all.append({"Paciente": hc_sel.get("nombre_paciente") or hc_sel["archivo"],
                    "Servicio": svc, "Estado": ic.get("estado_interconsulta", ""),
                    "Score": ic.get("score", 0), "Contar": ic.get("contar", False)})

    # Métricas resumen
    c1, c2, c3, c4 = st.columns(4)
    internacion = data.get("internacion", {})
    c1.metric("Intervenciones", data.get("total_intervenciones", "-"))
    c2.metric("Accuracy modelo", f"{data.get('modelo_nlp', {}).get('accuracy', 0.9298):.1%}")
    c3.metric("Días internación" if hc_sel else "Días prom.", internacion.get("dias_totales", "-"))
    c4.metric("Reingresos", internacion.get("reingresos", "-"))

    # Dos gráficos separados: áreas mayoritarias y minoritarias
    MAYORITARIAS = {"enfermeria", "psicologia"}
    areas = data.get("intervenciones_por_area", {})
    df_may = pd.DataFrame([{"Area": k, "N": v} for k, v in areas.items() if k in MAYORITARIAS]).sort_values("N", ascending=False)
    df_min = pd.DataFrame([{"Area": k, "N": v} for k, v in areas.items() if k not in MAYORITARIAS]).sort_values("N", ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Áreas mayoritarias")
        if not df_may.empty:
            ch = alt.Chart(df_may).mark_bar(color="#4C78A8").encode(
                x=alt.X("N:Q", title="Intervenciones"),
                y=alt.Y("Area:N", sort="-x", title=""),
                tooltip=["Area", "N"]
            ).properties(height=110)
            lb = alt.Chart(df_may).mark_text(align="left", dx=3, fontSize=13).encode(
                x="N:Q", y=alt.Y("Area:N", sort="-x"), text="N:Q"
            )
            st.altair_chart(ch + lb, use_container_width=True)
    with col2:
        st.subheader("Áreas minoritarias")
        if not df_min.empty:
            ch = alt.Chart(df_min).mark_bar(color="#F58518").encode(
                x=alt.X("N:Q", title="Intervenciones"),
                y=alt.Y("Area:N", sort="-x", title=""),
                tooltip=["Area", "N"]
            ).properties(height=max(160, len(df_min) * 38))
            lb = alt.Chart(df_min).mark_text(align="left", dx=3, fontSize=13).encode(
                x="N:Q", y=alt.Y("Area:N", sort="-x"), text="N:Q"
            )
            st.altair_chart(ch + lb, use_container_width=True)

    # Variables clínicas (solo HC individual)
    if vars_clinicas:
        presentes = [(k, v) for k, v in vars_clinicas.items() if v]
        if presentes:
            st.subheader("Variables clínicas detectadas")
            ca, cb = st.columns(2)
            for i, (k, _) in enumerate(presentes):
                (ca if i % 2 == 0 else cb).write(f"✅ {k.replace('_', ' ').capitalize()}")

    # Interconsultas de todas las HCs procesadas
    st.subheader(f"Interconsultas externas ({len(ics_all)})")
    if ics_all:
        df_ics = pd.DataFrame(ics_all).sort_values(["Score", "Contar"], ascending=[False, False])
        st.dataframe(df_ics, use_container_width=True, hide_index=True)
    else:
        st.info("No se detectaron interconsultas externas.")
elif modulo == "Reporte":
    st.title("Reporte Final - JSON")
    reps = requests.get(f"{API}/hcd/reportes")
    hcs = reps.json() if reps.status_code == 200 else []
    opciones = {f"{h['id']} - {h['archivo']}": h for h in hcs}
    sel = st.selectbox("Seleccionar HC", list(opciones.keys())) if opciones else None
    if sel:
        hc_sel = opciones[sel]
        try:
            data = json.loads(hc_sel["resumen"])
        except:
            data = {"resumen": hc_sel["resumen"]}
        st.json(data)
        st.download_button("Descargar JSON", json.dumps(data,ensure_ascii=False,indent=4), f"reporte_{hc_sel['archivo']}.json", "application/json")
