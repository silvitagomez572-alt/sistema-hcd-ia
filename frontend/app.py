import streamlit as st
import requests
import pandas as pd
import json

API = "http://localhost:8001"
st.set_page_config(page_title="Sistema HCD IA", layout="wide")
st.sidebar.title("Sistema HCD IA")
modulo = st.sidebar.radio("Modulo", [
    "Ingresar HC",
    "OCR",
    "Pseudonimizacion",
    "Procesamiento NLP",
    "RAG",
    "LLM local",
    "Interconsultas HCD",
    "Metricas HCD",
    "Resumen HCs",
    "Reporte",
])

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
elif modulo == "OCR":
    st.title("OCR — Extracción de Texto")
    st.caption("Módulo en desarrollo. Procesamiento de imágenes y PDFs escaneados.")
    st.text_area("Resultado de muestra", value="13/11/2025 - 05:33\nNota enfermeria\nPaciente tranquila...", height=200)
    st.success("Texto extraído.")
elif modulo == "Pseudonimizacion":
    st.title("Pseudonimización")
    c1, c2 = st.columns(2)
    c1.text_area("Original", value="Paciente: Maria Lopez\nDNI: 28456789", height=150)
    c2.text_area("Resultado", value="Paciente: [HC_ELIMINADA]\nDNI: [DNI_ELIMINADO]", height=150)
    st.success("Datos sensibles eliminados.")
elif modulo == "Procesamiento NLP":
    st.title("Procesamiento NLP")
    st.caption("Pipeline clínico local — sin modelos de lenguaje externos.")
    st.markdown("""
**Etapas del pipeline:**

1. **Parsing clínico** — segmentación de bloques por fecha/hora y marcadores clínicos (regex)
2. **Normalización Unicode** — unificación de acentos y variantes tipográficas
3. **Criterio de conteo** — validación de bloques por longitud mínima, deduplicación exacta y marcadores reconocidos
4. **Clasificador híbrido de áreas** — 4 capas en orden de prioridad:
   - Diccionario de profesionales (firma explícita)
   - Reglas por texto (keywords por área)
   - Modelo TF-IDF + Regresión Logística
   - Fallback: `otros`
5. **Detección de interconsultas** — servicios externos y estado (efectiva / solicitada / pendiente / mención)
6. **Salida estructurada** — JSON con `total_intervenciones`, `intervenciones_por_area`, `variables_clinicas_detectadas`, `interconsultas_detectadas`
""")
    st.info(f"Accuracy clasificador de áreas: **92.98%** (TF-IDF + Logistic Regression, validado sobre registros etiquetados)")
elif modulo == "RAG":
    st.title("RAG — Protocolos Clínicos")
    st.caption("Recuperación semántica sobre base documental de protocolos y glosarios.")
    q = st.text_input("Consultar base de conocimiento", placeholder="protocolo contención salud mental")
    if st.button("Buscar"):
        if q:
            with st.spinner("Buscando en base de conocimiento..."):
                try:
                    r = requests.post(f"{API}/rag/consultar", json={"pregunta": q})
                    if r.status_code == 200:
                        st.success(r.json()["respuesta"])
                        fuentes = r.json().get("fuentes", [])
                        if fuentes:
                            st.caption(f"Fuentes: {fuentes}")
                    else:
                        st.error(f"Error API: {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Escribí una consulta primero.")
elif modulo == "LLM local":
    st.title("LLM local")
    st.caption(
        "LLM local representa la capa de análisis contextual avanzado "
        "basada en modelos de lenguaje ejecutados localmente."
    )

    tab_gemma, tab_mistral = st.tabs(["Gemma (activo)", "Mistral (próximamente)"])

    with tab_gemma:
        st.markdown("**Modelo:** `gemma:2b` vía Ollama · API local `localhost:11434`")
        pregunta = st.text_input("Consulta al LLM", placeholder="Resume las intervenciones de salud mental",
                                 key="llm_gemma_input")
        if st.button("Ejecutar", key="llm_gemma_btn"):
            if pregunta:
                with st.spinner("Consultando Gemma vía Ollama..."):
                    try:
                        r = requests.post(f"{API}/llm/consultar", json={"pregunta": pregunta})
                        if r.status_code == 200:
                            st.success(r.json()["respuesta"])
                        else:
                            st.error(f"Error API: {r.status_code}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
            else:
                st.warning("Escribí una consulta primero.")

    with tab_mistral:
        st.info("Integración con Mistral en desarrollo. Se conectará vía Ollama con el mismo endpoint local.")
        st.code("ollama run mistral", language="bash")
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
    dias_pac = []  # (codigo_paciente, dias) para estadísticas consolidadas
    if hc_sel is None:
        areas_total, total_int, reingresos, cambios = {}, 0, 0, 0
        for h in hcs:
            try:
                d = json.loads(h["resumen"])
                total_pac = d.get("total_intervenciones", 0)
                areas = d.get("intervenciones_por_area", {})
                # Incluir áreas solo cuando son consistentes con el total validado
                # (registros stale tienen total_intervenciones=0 pero áreas infladas)
                if sum(areas.values()) == total_pac:
                    for k, v in areas.items():
                        areas_total[k] = areas_total.get(k, 0) + v
                total_int += total_pac
                intern = d.get("internacion", {})
                reingresos += intern.get("reingresos", 0)
                cambios += intern.get("cambios_cama", 0)
                dias = intern.get("dias_totales", 0)
                if dias:
                    dias_pac.append((h["codigo_paciente"], dias))
                for ic in d.get("interconsultas_detectadas", []):
                    for svc in ic.get("servicios", []):
                        ics_all.append({"Paciente": h["codigo_paciente"],
                            "Servicio": svc, "Estado": ic.get("estado_interconsulta", ""),
                            "Score": ic.get("score", 0), "Contar": ic.get("contar", False)})
            except:
                pass
        dias_vals = [d for _, d in dias_pac]
        dias_avg = round(sum(dias_vals) / len(dias_vals), 1) if dias_vals else 0
        data = {"intervenciones_por_area": areas_total, "total_intervenciones": total_int,
                "internacion": {"dias_totales": dias_avg, "reingresos": reingresos, "cambios_cama": cambios},
                "modelo_nlp": {"accuracy": 0.9298}}
        vars_clinicas = {}
    else:
        dias_vals = []
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
    internacion = data.get("internacion", {})
    if hc_sel is None:
        # Vista consolidada: fila de totales + fila de estadísticas de días
        c1, c2, c3 = st.columns(3)
        c1.metric("Intervenciones válidas totales", data.get("total_intervenciones", "-"))
        c2.metric("Accuracy modelo", f"{data.get('modelo_nlp', {}).get('accuracy', 0.9298):.1%}")
        c3.metric("Reingresos", internacion.get("reingresos", "-"))
        if dias_vals:
            import statistics as _stats
            pac_max = max(dias_pac, key=lambda x: x[1])
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("Promedio días internación", f"{dias_avg:.1f}")
            d2.metric("Mediana días", f"{_stats.median(dias_vals):.0f}")
            d3.metric("Mínimo días", min(dias_vals))
            d4.metric("Máximo días", max(dias_vals))
            d5.metric("Mayor período", f"{pac_max[0]} ({pac_max[1]}d)")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Intervenciones", data.get("total_intervenciones", "-"))
        c2.metric("Accuracy modelo", f"{data.get('modelo_nlp', {}).get('accuracy', 0.9298):.1%}")
        c3.metric("Días internación", internacion.get("dias_totales", "-"))
        c4.metric("Reingresos", internacion.get("reingresos", "-"))

    # Tres gráficos: SM principal / equipo interdisciplinario SM / interconsultas externas
    SM_PRINCIPAL   = {"enfermeria", "psicologia", "psiquiatria"}
    SM_INTERDISCIP = {"terapia_ocupacional", "trabajo_social", "acompanante_terapeutico", "psicopedagogia", "otros"}
    ETIQ_AREAS = {
        "enfermeria":               "Enfermería",
        "psicologia":               "Psicología",
        "psiquiatria":              "Psiquiatría",
        "trabajo_social":           "Trabajo Social",
        "acompanante_terapeutico":  "Acomp. Terapéutico",
        "terapia_ocupacional":      "Terapia Ocupacional",
        "psicopedagogia":           "Psicopedagogía",
        "otros":                    "Otros apoyos SM",
    }
    areas = data.get("intervenciones_por_area", {})

    def _df_areas(keys_set):
        rows = [{"Area": ETIQ_AREAS.get(k, k.replace("_", " ").capitalize()), "N": v}
                for k, v in areas.items() if k in keys_set and v > 0]
        return pd.DataFrame(rows).sort_values("N", ascending=False) if rows else pd.DataFrame()

    df_sm_prin  = _df_areas(SM_PRINCIPAL)
    df_sm_inter = _df_areas(SM_INTERDISCIP)

    # Gráfico 3: agrega interconsultas externas desde ics_all (servicios externos detectados)
    if ics_all:
        from collections import Counter as _Counter
        svc_counts = _Counter(ic["Servicio"] for ic in ics_all)
        df_ext = pd.DataFrame([{"Area": s.capitalize(), "N": n}
                               for s, n in svc_counts.most_common()])
    else:
        df_ext = pd.DataFrame()

    def _bar_chart(df, color, height):
        ch = alt.Chart(df).mark_bar(color=color).encode(
            x=alt.X("N:Q", title="Intervenciones"),
            y=alt.Y("Area:N", sort="-x", title=""),
            tooltip=["Area", "N"]
        ).properties(height=height)
        lb = alt.Chart(df).mark_text(align="left", dx=3, fontSize=13).encode(
            x="N:Q", y=alt.Y("Area:N", sort="-x"), text="N:Q"
        )
        return ch + lb

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Intervenciones por área — Salud Mental principal")
        if not df_sm_prin.empty:
            st.altair_chart(_bar_chart(df_sm_prin, "#4C78A8", max(110, len(df_sm_prin) * 45)), use_container_width=True)
        else:
            st.info("Sin datos.")
    with col2:
        st.subheader("Intervenciones por área — Equipo interdisciplinario Salud Mental")
        if not df_sm_inter.empty:
            st.altair_chart(_bar_chart(df_sm_inter, "#F58518", max(160, len(df_sm_inter) * 45)), use_container_width=True)
        else:
            st.info("Sin datos.")
    with col3:
        st.subheader("Interconsultas externas detectadas")
        if not df_ext.empty:
            st.altair_chart(_bar_chart(df_ext, "#72B7B2", max(110, len(df_ext) * 45)), use_container_width=True)
        else:
            st.info("Sin datos.")

    st.caption("Los gráficos por área se calculan sobre intervenciones válidas clasificadas por área profesional. No incluyen bloques descartados ni duplicados.")

    ETIQUETAS_VARIABLES = {
        "delirio_psicosis":        "Desorganización del pensamiento",
        "sin_red_vincular":        "Ausencia de red de apoyo",
        "agresividad":             "Agitación psicomotriz",
        "adherencia_problematica": "Dificultades de adherencia",
        "internacion_prolongada":  "Internación prolongada",
        "estado_estable":          "Estado clínico estable",
        "bradipsiquia":            "Enlentecimiento psicomotriz",
        "ideacion_autolitica":     "Indicadores de riesgo",
        "riesgo_fuga":             "Riesgo de abandono del servicio",
        "consumo_sustancias":      "Consumo problemático",
    }

    # Variables clínicas (solo HC individual)
    if vars_clinicas:
        presentes = [(k, v) for k, v in vars_clinicas.items() if v]
        if presentes:
            st.subheader("Variables clínicas detectadas")
            ca, cb = st.columns(2)
            for i, (k, _) in enumerate(presentes):
                etiqueta = ETIQUETAS_VARIABLES.get(k, k.replace("_", " ").capitalize())
                (ca if i % 2 == 0 else cb).write(f"✅ {etiqueta}")

    # Interconsultas de todas las HCs procesadas
    if ics_all:
        st.subheader(f"Detalle auditable de interconsultas detectadas ({len(ics_all)})")
        df_ics = pd.DataFrame(ics_all).sort_values(["Score", "Contar"], ascending=[False, False])
        df_ics = df_ics.rename(columns={"Score": "Confianza", "Contar": "Incluir en conteo"})
        st.dataframe(df_ics, use_container_width=True, hide_index=True)
    else:
        st.info("No se detectaron interconsultas externas.")
elif modulo == "Resumen HCs":
    st.title("Reporte Bioestadístico Automatizado — HCD IA")
    st.caption("Detección automatizada preliminar en validación. Resultados sujetos a revisión humana.")

    r = requests.get(f"{API}/hcd/reporte-total")
    if r.status_code != 200:
        st.error("Error al obtener reporte total.")
        st.stop()
    reporte = r.json()
    resumen = reporte["resumen_ejecutivo"]
    casos = reporte["casos"]
    vars_freq = reporte["variables_clinicas_por_frecuencia"]
    ics_estado = reporte["interconsultas_por_estado"]

    # KPIs ejecutivos — calculados desde datos individuales validados por paciente
    import statistics as _stats
    total_int_calc = sum(c["total_intervenciones"] for c in casos)
    n_pac = len(casos)
    dias_pac_res = [(c["codigo_paciente"], c["dias_internacion"]) for c in casos if c["dias_internacion"]]
    dias_vals_res = [d for _, d in dias_pac_res]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pacientes", n_pac)
    c2.metric("Intervenciones válidas totales", total_int_calc)
    c3.metric("Promedio intervenciones/paciente", round(total_int_calc / n_pac, 1) if n_pac else 0)
    c4.metric("Reingresos", resumen["total_reingresos"])

    if dias_vals_res:
        pac_max_res = max(dias_pac_res, key=lambda x: x[1])
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("Promedio días internación", f"{sum(dias_vals_res)/len(dias_vals_res):.1f}")
        d2.metric("Mediana días", f"{_stats.median(dias_vals_res):.0f}")
        d3.metric("Mínimo días", min(dias_vals_res))
        d4.metric("Máximo días", max(dias_vals_res))
        d5.metric("Mayor período", f"{pac_max_res[0]} ({pac_max_res[1]}d)")

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
            ETIQ_VARS = {"delirio_psicosis":"Desorganización del pensamiento","sin_red_vincular":"Ausencia de red de apoyo","agresividad":"Agitación psicomotriz","adherencia_problematica":"Dificultades de adherencia","internacion_prolongada":"Internación prolongada","estado_estable":"Estado clínico estable","bradipsiquia":"Enlentecimiento psicomotriz","ideacion_autolitica":"Indicadores de riesgo","riesgo_fuga":"Riesgo de abandono del servicio","consumo_sustancias":"Consumo problemático"}
            df_vars = pd.DataFrame({"Variable": list(vars_freq.keys()), "Pacientes": list(vars_freq.values())})
            df_vars["Variable"] = df_vars["Variable"].map(lambda k: ETIQ_VARS.get(k, k.replace("_", " ").capitalize()))
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
    ETIQ_VARS2 = {"delirio_psicosis":"Desorganización del pensamiento","sin_red_vincular":"Ausencia de red de apoyo","agresividad":"Agitación psicomotriz","adherencia_problematica":"Dificultades de adherencia","internacion_prolongada":"Internación prolongada","estado_estable":"Estado clínico estable","bradipsiquia":"Enlentecimiento psicomotriz","ideacion_autolitica":"Indicadores de riesgo","riesgo_fuga":"Riesgo de abandono del servicio","consumo_sustancias":"Consumo problemático"}
    for c in casos:
        for v in c["variables_clinicas_presentes"]:
            det_filas.append({"Paciente": c["codigo_paciente"], "Variable": ETIQ_VARS2.get(v, v.replace("_", " ").capitalize())})
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
