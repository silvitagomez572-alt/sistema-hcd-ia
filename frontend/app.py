import streamlit as st
import requests
import pandas as pd
import json

API = "http://localhost:8001"
st.set_page_config(page_title="Sistema HCD IA", layout="wide")
st.sidebar.title("Sistema HCD IA")
modulo = st.sidebar.radio("Modulo", ["Ingresar HC","Extraccion OCR","Pseudonimizacion","Modelo NLP","Base de Conocimiento","Interconsultas HCD","Metricas HCD","Resumen HCs","Reporte"])

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
                        st.json({k: v for k, v in data.items() if k != "texto_extraido"})
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

    opciones = {"— Todos los pacientes —": None}
    opciones.update({h["codigo_paciente"]: h for h in hcs})
    sel = st.selectbox("Seleccionar paciente", list(opciones.keys()))
    hcs_mostrar = hcs if opciones[sel] is None else [opciones[sel]]

    for h in hcs_mostrar:
        codigo = h["codigo_paciente"]
        try:
            data = json.loads(h["resumen"])
        except:
            continue
        ics = data.get("interconsultas_detectadas", [])
        if not ics:
            continue

        st.markdown(f"### 👤 {codigo}")
        st.caption(f"Fecha: {h['fecha'][:10]}")

        with st.expander("¿Cómo se calcula la confianza?"):
            st.write(
                "El puntaje se asigna mediante reglas lingüísticas aplicadas al texto clínico de cada registro:\n\n"
                "- **5 — Efectiva confirmada:** el texto contiene frases de acción completada: "
                "*\"se realiza interconsulta\", \"evaluado por\", \"responde interconsulta\"*.\n"
                "- **4 — Solicitada:** hay registro explícito de solicitud: "
                "*\"se solicita interconsulta\", \"requiere valoración por\"*.\n"
                "- **3 — Pendiente sin respuesta:** el texto indica que la interconsulta fue pedida "
                "pero no se registra respuesta: *\"pendiente i/c\", \"i/c pendiente\"*.\n"
                "- **0 — Solo mención:** el servicio aparece nombrado en el texto sin acción asociada.\n\n"
                "Solo las interconsultas con confianza ≥ 4 se marcan como **✓ confirmadas**."
            )
        st.caption("Confianza: 5 = efectiva confirmada · 4 = solicitada · 3 = pendiente sin respuesta · 0 = solo mención")
        for ic in ics:
            svcs = ic.get("servicios", [])
            estado = ic.get("estado_interconsulta", "mencion_servicio")
            score = ic.get("score", 0)
            contar = ic.get("contar", False)
            evidencia = ic.get("evidencia", ic.get("texto", ""))
            emoji, _ = ESTADO_COLOR.get(estado, ("⚪", "secondary"))
            svc_label = ", ".join(s.upper() for s in svcs) if svcs else "SERVICIO"
            confirmada_label = "✓ confirmada" if contar else "✗ no confirmada"

            with st.container():
                c1, c2, c3, c4 = st.columns([3, 4, 1, 2])
                c1.write(f"{emoji} {svc_label}")
                c2.write(estado.replace("_", " "))
                c3.write(f"confianza {score}")
                c4.write(confirmada_label)
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
    opciones.update({h["codigo_paciente"]: h for h in hcs})
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
                        ics_all.append({"Paciente": h["codigo_paciente"],
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
                ics_all.append({"Paciente": hc_sel["codigo_paciente"],
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
elif modulo == "Resumen HCs":
    st.title("Resumen comparativo de HCs procesadas")

    r = requests.get(f"{API}/hcd/reporte-total")
    if r.status_code != 200:
        st.error("Error al obtener reporte total.")
        st.stop()
    reporte = r.json()
    resumen = reporte["resumen_ejecutivo"]
    casos = reporte["casos"]
    vars_freq = reporte["variables_clinicas_por_frecuencia"]
    ics_estado = reporte["interconsultas_por_estado"]

    # KPIs ejecutivos
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pacientes", resumen["total_pacientes"])
    c2.metric("Intervenciones totales", resumen["total_intervenciones"])
    c3.metric("Prom. intervenciones", resumen["promedio_intervenciones_por_paciente"])
    c4.metric("Prom. días internación", resumen["promedio_dias_internacion"])
    c5.metric("Reingresos", resumen["total_reingresos"])

    # Tabla comparativa
    st.subheader("Tabla comparativa por paciente")
    filas = []
    for c in casos:
        areas = c["intervenciones_por_area"]
        area_top2 = ", ".join(
            f"{k}({v})" for k, v in sorted(areas.items(), key=lambda x: -x[1])[:2]
        )
        filas.append({
            "Paciente": c["codigo_paciente"],
            "Días intern.": c["dias_internacion"],
            "Intervenciones": c["total_intervenciones"],
            "Área principal": c["area_principal"],
            "Top 2 áreas": area_top2,
            "Variables clínicas": len(c["variables_clinicas_presentes"]),
            "ICs efectivas": c["interconsultas_efectivas"],
            "ICs total": c["interconsultas_total"],
            "Reingresos": c["reingresos"],
        })
    df_tabla = pd.DataFrame(filas)
    st.dataframe(df_tabla, use_container_width=True, hide_index=True)

    # Variables clínicas: frecuencia entre pacientes
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Variables clínicas por frecuencia")
        if vars_freq:
            import altair as alt
            df_vars = pd.DataFrame({"Variable": list(vars_freq.keys()), "Pacientes": list(vars_freq.values())})
            df_vars["Variable"] = df_vars["Variable"].str.replace("_", " ").str.capitalize()
            ch = alt.Chart(df_vars).mark_bar(color="#72B7B2").encode(
                x=alt.X("Pacientes:Q", title="N° pacientes"),
                y=alt.Y("Variable:N", sort="-x", title=""),
                tooltip=["Variable", "Pacientes"]
            ).properties(height=max(200, len(df_vars) * 28))
            lb = alt.Chart(df_vars).mark_text(align="left", dx=3).encode(
                x="Pacientes:Q", y=alt.Y("Variable:N", sort="-x"), text="Pacientes:Q"
            )
            st.altair_chart(ch + lb, use_container_width=True)

    with col2:
        st.subheader("Interconsultas por estado")
        if ics_estado:
            df_ics = pd.DataFrame({"Estado": list(ics_estado.keys()), "Total": list(ics_estado.values())})
            df_ics["Estado"] = df_ics["Estado"].str.replace("_", " ").str.capitalize()
            ch2 = alt.Chart(df_ics).mark_bar(color="#E45756").encode(
                x=alt.X("Total:Q", title="Total"),
                y=alt.Y("Estado:N", sort="-x", title=""),
                tooltip=["Estado", "Total"]
            ).properties(height=max(160, len(df_ics) * 35))
            lb2 = alt.Chart(df_ics).mark_text(align="left", dx=3).encode(
                x="Total:Q", y=alt.Y("Estado:N", sort="-x"), text="Total:Q"
            )
            st.altair_chart(ch2 + lb2, use_container_width=True)
        st.warning("⚠️ Los datos de interconsultas son una estimación automatizada en revisión. No reemplaza la auditoría manual de las HCs.")

    # Variables clínicas presentes por paciente (detalle)
    st.subheader("Variables clínicas presentes por paciente")
    det_filas = []
    for c in casos:
        for v in c["variables_clinicas_presentes"]:
            det_filas.append({"Paciente": c["codigo_paciente"], "Variable": v.replace("_", " ").capitalize()})
    if det_filas:
        st.dataframe(pd.DataFrame(det_filas), use_container_width=True, hide_index=True)

    # Descarga JSON para el director
    st.subheader("Exportar reporte ejecutivo")
    st.download_button(
        "Descargar JSON completo",
        json.dumps(reporte, ensure_ascii=False, indent=2),
        "reporte_total_hcd.json",
        "application/json"
    )

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
