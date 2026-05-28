import streamlit as st
import requests
import pandas as pd
import json

API = "http://localhost:8001"
st.set_page_config(page_title="Sistema HCD IA", layout="wide")
st.sidebar.title("Sistema HCD IA")
modulo = st.sidebar.radio("Modulo", [
    "📋 Censo Mensual",
    "Ingresar HC",
    "OCR",
    "Pseudonimizacion",
    "Procesamiento NLP",
    "RAG",
    "LLM local",
    "Interconsultas HCD",
    "Metricas HCD",
    "Resumen HCs",
    "Auditoría",
    "Informe",
])

if modulo == "📋 Censo Mensual":
    import sys as _sys
    import pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
    try:
        from pipeline.censo.modulo_censo_mensual import leer_archivo_censo, filtrar_salud_mental, stats_servicio_sm, TOTAL_CAMAS_FIJAS
        _censo_ok = True
    except ImportError as _e:
        _censo_ok = False
        _censo_err = str(_e)

    st.title("📋 Censo Mensual — Salud Mental")

    if not _censo_ok:
        st.error(f"Módulo de censo no disponible: {_censo_err}")
        st.stop()

    for _k in ("censo_df", "censo_raw_stats"):
        if _k not in st.session_state:
            st.session_state[_k] = None

    tab_carga, tab_stats, tab_pendientes = st.tabs(
        ["📥 Cargar Censos", "📊 Estadísticas", "⏳ Pendientes"]
    )

    with tab_carga:
        st.subheader("Cargar archivos de censo VADIGU")
        archivos_cargados = st.file_uploader(
            "Seleccionar uno o varios archivos del mes",
            type=["csv", "xlsx", "xls", "html", "htm", "pdf"],
            accept_multiple_files=True,
            key="censo_uploader",
        )

        if archivos_cargados and st.button("Consolidar mes", key="censo_btn"):
            import tempfile
            fragmentos, stats_lista, errores = [], [], []
            with tempfile.TemporaryDirectory() as _tmpdir:
                for _arch in archivos_cargados:
                    _ruta_tmp = _pl.Path(_tmpdir) / _arch.name
                    _ruta_tmp.write_bytes(_arch.getvalue())
                    try:
                        _df_raw = leer_archivo_censo(_ruta_tmp)
                        _svc = stats_servicio_sm(_df_raw)
                        _ocu = _svc["ocupadas_fijas"]
                        _lib = _svc["libres_fijas"]
                        _trans_ocu = _svc["transitorias_ocupadas"]
                        _df_sm = filtrar_salud_mental(_df_raw)
                        stats_lista.append({"Archivo": _arch.name, "Total SM (18 fijas)": TOTAL_CAMAS_FIJAS, "Ocupadas": _ocu, "Libres": _lib, "Transitoria - Trasplantados": _trans_ocu})
                        if not _df_sm.empty:
                            _df_sm = _df_sm.copy()
                            _df_sm["_archivo"] = _arch.name
                            fragmentos.append(_df_sm)
                    except Exception as _exc:
                        errores.append((_arch.name, str(_exc)))

            for _nombre, _msg in errores:
                st.warning(f"⚠️ {_nombre}: {_msg}")

            if fragmentos:
                _df_cons = pd.concat(fragmentos, ignore_index=True)
                if "codigoHC" in _df_cons.columns:
                    if "Ingreso" in _df_cons.columns:
                        _df_cons["Ingreso"] = pd.to_datetime(_df_cons["Ingreso"], unit='ms', errors="coerce")
                        _df_cons = _df_cons.sort_values("Ingreso", na_position="first")
                    _df_cons = _df_cons.drop_duplicates(subset=["codigoHC"], keep="last").reset_index(drop=True)
                st.session_state["censo_df"] = _df_cons
                st.session_state["censo_raw_stats"] = pd.DataFrame(stats_lista)
                st.success(f"{len(archivos_cargados)} archivo(s) → {len(_df_cons)} pacientes únicos en Salud Mental.")
            else:
                st.warning("No se encontraron filas con Estado=Ocupada y Area=Salud Mental.")

        if st.session_state["censo_raw_stats"] is not None:
            _df_st = st.session_state["censo_raw_stats"]
            _df_cons2 = st.session_state["censo_df"]
            _n_sm = len(_df_cons2) if _df_cons2 is not None else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Internados SM (únicos/mes)", _n_sm)
            c2.metric("Pico camas fijas SM ocupadas", int(_df_st["Ocupadas"].max()))
            c3.metric("Pico camas fijas SM libres", int(_df_st["Libres"].max()))
            st.subheader("Detalle por archivo")
            st.dataframe(_df_st, width='stretch', hide_index=True)

            if _df_cons2 is not None and not _df_cons2.empty:
                st.divider()
                st.warning("⚠️ Información de uso interno — no compartir")
                _cols_dedup = [c for c in ["codigoHC", "Paciente", "Documento", "Ingreso", "Estada", "Area", "tipo_cama"] if c in _df_cons2.columns]
                if _cols_dedup:
                    st.subheader("Pacientes internados — Salud Mental")
                    st.caption("Consultá VADIGU para identificar el paciente por codigoHC.")
                    _df_tabla = _df_cons2[_cols_dedup].copy()
                    # Deduplicar por Documento (DNI) conservando el registro con mayor Estada.
                    # El mismo paciente puede tener dos codigoHC distintos en VADIGU.
                    if "Estada" in _df_tabla.columns:
                        _df_tabla["Estada"] = pd.to_numeric(_df_tabla["Estada"], errors="coerce").fillna(0)
                        _dedup_col = "Documento" if "Documento" in _df_tabla.columns else "codigoHC"
                        _df_tabla = (
                            _df_tabla
                            .sort_values("Estada", ascending=False)
                            .drop_duplicates(subset=[_dedup_col], keep="first")
                            .sort_values("Estada", ascending=False)
                            .reset_index(drop=True)
                        )
                        _df_tabla["Estada"] = _df_tabla["Estada"].astype(int).astype(str)
                    if "Ingreso" in _df_tabla.columns:
                        _df_tabla["Ingreso"] = pd.to_datetime(_df_tabla["Ingreso"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
                    # Solo pantalla — Documento visible pero no se persiste en ningún lado
                    _cols_visibles = [c for c in ["codigoHC", "Documento", "Ingreso", "Estada", "tipo_cama"] if c in _df_tabla.columns]
                    st.dataframe(
                        _df_tabla[_cols_visibles],
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "codigoHC":  st.column_config.TextColumn("codigoHC",  width="medium"),
                            "Documento": st.column_config.TextColumn("Documento", width="medium"),
                            "Ingreso":   st.column_config.TextColumn("Ingreso",   width="small"),
                            "Estada":    st.column_config.TextColumn("Estada",    width="small"),
                            "tipo_cama": st.column_config.TextColumn("Tipo cama", width="medium"),
                        },
                    )

    with tab_stats:
        st.subheader("Estadísticas del mes")
        _df_censo = st.session_state["censo_df"]
        if _df_censo is None or _df_censo.empty:
            st.info("Primero cargá los archivos en la pestaña **📥 Cargar Censos**.")
        else:
            _df_st2 = st.session_state.get("censo_raw_stats")
            _n_pac = len(_df_censo)

            _porc_ocu = None
            if _df_st2 is not None and "Ocupadas" in _df_st2.columns:
                _porc_ocu = round(100 * _df_st2["Ocupadas"].mean() / TOTAL_CAMAS_FIJAS, 1)

            _prom_estada = None
            if "Estada" in _df_censo.columns:
                _estada_num = pd.to_numeric(_df_censo["Estada"], errors="coerce").dropna()
                if not _estada_num.empty:
                    _prom_estada = round(float(_estada_num.mean()), 1)

            _giro = None
            if _df_st2 is not None and "Ocupadas" in _df_st2.columns and _df_st2["Ocupadas"].max() > 0:
                _giro = round(_n_pac / _df_st2["Ocupadas"].max(), 2)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total pacientes SM", _n_pac)
            c2.metric("% Ocupación SM", f"{_porc_ocu}%" if _porc_ocu is not None else "N/D")
            c3.metric("Promedio estada (días)", _prom_estada if _prom_estada is not None else "N/D")
            c4.metric("Giro camas", _giro if _giro is not None else "N/D")

            if _df_st2 is not None and len(_df_st2) > 1:
                import altair as alt
                import re as _re2
                def _ext_fecha(nombre):
                    _m = _re2.search(r'(\d{2}[-_/]\d{2}[-_/]\d{4}|\d{4}[-_/]\d{2}[-_/]\d{2})', nombre)
                    return _m.group(1).replace("_", "/").replace("-", "/") if _m else nombre
                _df_chart = _df_st2[["Archivo", "Ocupadas"]].copy()
                _df_chart["Día"] = _df_chart["Archivo"].map(_ext_fecha)
                st.subheader("Ocupación SM por día")
                _ch = (
                    alt.Chart(_df_chart)
                    .mark_line(point=True, color="#4C78A8")
                    .encode(
                        x=alt.X("Día:N", title="Día / Archivo", sort=None),
                        y=alt.Y("Ocupadas:Q", title="Camas fijas SM ocupadas"),
                        tooltip=["Día", "Ocupadas"],
                    )
                    .properties(height=260)
                )
                st.altair_chart(_ch, use_container_width=True)

    with tab_pendientes:
        st.subheader("HCs pendientes de procesamiento")
        _df_censo = st.session_state["censo_df"]
        if _df_censo is None or _df_censo.empty:
            st.info("Primero cargá los archivos en la pestaña **📥 Cargar Censos**.")
        elif "codigoHC" not in _df_censo.columns:
            st.warning("Los archivos cargados no contienen la columna 'codigoHC'.")
        else:
            try:
                _r_proc = requests.get(f"{API}/hcd/reportes", timeout=10)
                _procesadas = set()
                if _r_proc.status_code == 200:
                    for _rep in _r_proc.json():
                        _procesadas.add(_rep.get("archivo", "").lower())
                        _procesadas.add(_rep.get("codigo_paciente", "").lower())
            except Exception:
                _procesadas = set()

            _filas = []
            for _, _pac_row in _df_censo.iterrows():
                _cod = str(_pac_row.get("codigoHC", "")).strip()
                _nombre = str(_pac_row.get("Paciente", "—")).strip()
                _ya_proc = any(_cod.lower() in _p for _p in _procesadas)
                _filas.append({
                    "codigoHC": _cod,
                    "Paciente": _nombre,
                    "Estado": "✅ Procesado" if _ya_proc else "⏳ Pendiente",
                })

            _df_pend = pd.DataFrame(_filas)
            _n_proc = int((_df_pend["Estado"] == "✅ Procesado").sum())
            _n_pend = int((_df_pend["Estado"] == "⏳ Pendiente").sum())
            cp1, cp2 = st.columns(2)
            cp1.metric("Procesados", _n_proc)
            cp2.metric("Pendientes", _n_pend)

            _filtro_p = st.radio(
                "Mostrar",
                ["Todos", "Solo pendientes", "Solo procesados"],
                horizontal=True,
                key="censo_filtro_p",
            )
            if _filtro_p == "Solo pendientes":
                _df_vis = _df_pend[_df_pend["Estado"] == "⏳ Pendiente"]
            elif _filtro_p == "Solo procesados":
                _df_vis = _df_pend[_df_pend["Estado"] == "✅ Procesado"]
            else:
                _df_vis = _df_pend
            st.dataframe(_df_vis, width='stretch', hide_index=True)

            _solo_pend = _df_pend[_df_pend["Estado"] == "⏳ Pendiente"]
            if not _solo_pend.empty:
                st.download_button(
                    "Descargar pendientes (CSV)",
                    _solo_pend.to_csv(index=False),
                    "hcs_pendientes.csv",
                    "text/csv",
                    key="censo_dl_pend",
                )

elif modulo == "Ingresar HC":
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
    st.caption("Recuperación semántica sobre base documental de protocolos y glosarios institucionales.")

    tab_docs, tab_busqueda = st.tabs(["📂 Documentos", "🔍 Búsqueda semántica"])

    with tab_docs:
        st.subheader("Base documental")
        st.caption(
            "Tipos de documentos admitidos: Ley N° 26.657, protocolos clínicos, "
            "guías OMS/mhGAP, criterios institucionales, glosarios."
        )
        try:
            resp_docs = requests.get(f"{API}/rag/documentos", timeout=10)
            docs = resp_docs.json() if resp_docs.status_code == 200 else []
        except Exception as e:
            docs = []
            st.error(f"Error al obtener documentos: {e}")

        if docs:
            rows = []
            for d in docs:
                rows.append({
                    "Archivo": d["nombre"],
                    "Tipo": d["tipo"],
                    "Tamaño (KB)": d["tamano_kb"],
                    "Estado": "✅ Indexado" if d["indexado"] else "⏳ Pendiente",
                })
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        else:
            st.info("No hay documentos cargados aún.")

        st.divider()
        st.subheader("Cargar nuevo documento")
        archivo_up = st.file_uploader(
            "Seleccionar archivo",
            type=["pdf", "txt", "docx"],
            key="rag_upload",
        )
        if archivo_up and st.button("Subir documento", key="rag_subir_btn"):
            with st.spinner("Subiendo..."):
                try:
                    r = requests.post(
                        f"{API}/rag/subir",
                        files={"archivo": (archivo_up.name, archivo_up.getvalue(), archivo_up.type)},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        st.success(f"Documento '{archivo_up.name}' guardado. Estado: pendiente de indexación.")
                        st.rerun()
                    else:
                        st.error(f"Error al subir: {r.status_code}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    with tab_busqueda:
        st.subheader("Búsqueda semántica")
        q = st.text_input(
            "Consultar base de conocimiento",
            placeholder="protocolo contención salud mental",
            key="rag_query",
        )
        if st.button("Buscar", key="rag_buscar_btn"):
            if q:
                with st.spinner("Buscando en base de conocimiento..."):
                    try:
                        r = requests.post(f"{API}/rag/consultar", json={"pregunta": q})
                        if r.status_code == 200:
                            data_rag = r.json()
                            st.success(data_rag["respuesta"])
                            fuentes = data_rag.get("fuentes", [])
                            if fuentes:
                                with st.expander("Fuentes recuperadas"):
                                    for f in fuentes:
                                        st.caption(str(f))
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
        st.dataframe(df_ics, width='stretch', hide_index=True)
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
    st.dataframe(df_tabla, width='stretch', hide_index=True)

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
        st.dataframe(pd.DataFrame(det_filas), width='stretch', hide_index=True)

    # Descarga JSON para el director
    st.subheader("Exportar reporte ejecutivo")
    st.download_button(
        "Descargar JSON completo",
        json.dumps(reporte, ensure_ascii=False, indent=2),
        "reporte_total_hcd.json",
        "application/json"
    )

elif modulo == "Auditoría":
    st.title("Auditoría clínica y trazabilidad")
    st.caption("Estado del pipeline de procesamiento y calidad por historia clínica.")

    import subprocess

    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        git_commit = "N/A"

    reps_r = requests.get(f"{API}/hcd/reportes")
    all_rows = reps_r.json() if reps_r.status_code == 200 else []

    rt_r = requests.get(f"{API}/hcd/reporte-total")
    reporte_t = rt_r.json() if rt_r.status_code == 200 else {}
    casos = reporte_t.get("casos", [])

    # Deduplicar por archivo: mismo criterio que reporte-total (MAX id)
    seen_r = {}
    for h in all_rows:
        arch = h["archivo"]
        if arch not in seen_r or h["id"] > seen_r[arch]["id"]:
            seen_r[arch] = h
    rows_dedup = list(seen_r.values())

    # Candidatos, descartados, stale
    candidatos_total = 0
    intervenciones_total = 0
    ics_total = 0
    stale_rows = []

    for h in rows_dedup:
        try:
            d = json.loads(h["resumen"])
        except Exception:
            stale_rows.append(h)
            continue
        total_pac = d.get("total_intervenciones", 0)
        raw_pac = d.get("total_registros_raw", 0)
        areas = d.get("intervenciones_por_area", {})
        if not (total_pac > 0 and sum(areas.values()) == total_pac):
            stale_rows.append(h)
            continue
        candidatos_total += raw_pac
        intervenciones_total += total_pac
        ics_total += len(d.get("interconsultas_detectadas", []))

    descartados_total = candidatos_total - intervenciones_total

    # Última fecha de procesamiento (de los válidos)
    fechas_validas = []
    for h in rows_dedup:
        f = h.get("fecha", "")
        if f and not f.startswith("{"):
            fechas_validas.append(f[:19])
    ultima_fecha = max(fechas_validas) if fechas_validas else "N/A"

    # --- Expander de pipeline ---
    with st.expander("🔍 Información del pipeline", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Versión del pipeline:** `1.0.0`")
            st.markdown(f"**Commit activo:** `{git_commit}`")
            st.markdown(f"**Último procesamiento:** `{ultima_fecha}`")
        with col2:
            st.markdown("**Modelo NLP:** TF-IDF + Logistic Regression")
            st.markdown("**Accuracy:** 92.98%")
            st.markdown("**Clasificador:** 4 capas (diccionario → reglas → NLP → fallback)")

    # --- Métricas de auditoría ---
    st.subheader("Resumen de procesamiento")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Pacientes válidos", len(casos))
    m2.metric("Candidatos iniciales", candidatos_total)
    m3.metric("Descartados", descartados_total)
    m4.metric("Intervenciones finales", intervenciones_total)
    m5.metric("ICs detectadas", ics_total)
    m6.metric("Stale excluidos", len(stale_rows))

    # Enriquecer casos con raw count y raw hash desde rows_dedup
    raw_por_arch = {}
    for h in rows_dedup:
        try:
            d = json.loads(h["resumen"])
            raw_por_arch[h["archivo"]] = d.get("total_registros_raw", 0) or 0
        except Exception:
            raw_por_arch[h["archivo"]] = 0

    # --- Semáforo calibrado ---
    # 🔴 Inconsistente real: stale/JSON inválido, duplicado real (contenido idéntico)
    # 🟡 Revisar cálculo/metodología: artefacto temporal VADIGU (tasa aparente baja),
    #             internación > 365 días (outlier de duración)
    # 🟢 Consistente: ninguna condición anterior
    # NO son criterios: psiquiatría=0, enfermería dominante, HC corta con tasa alta
    # (son patrones estructurales de VADIGU, no inconsistencias clínicas)

    def _semaforo_hc(caso, todos_los_casos):
        total = caso["total_intervenciones"]
        dias  = caso.get("dias_internacion") or 0
        areas = caso.get("intervenciones_por_area", {})
        raw   = raw_por_arch.get(caso.get("archivo", ""), 0)
        tasa  = round(total / dias, 3) if dias else None

        # 🔴 Duplicado real: otro caso con total, áreas e internación idénticos
        for otro in todos_los_casos:
            if otro["codigo_paciente"] == caso["codigo_paciente"]:
                continue
            if (otro["total_intervenciones"] == total
                    and otro.get("intervenciones_por_area") == areas
                    and otro.get("dias_internacion") == dias):
                return "🔴", [f"Duplicado real de {otro['codigo_paciente']} — contenido idéntico"]

        alertas = []
        # 🟡 Tasa aparente muy baja: probable artefacto del rango de fechas VADIGU
        if tasa is not None and tasa < 0.3 and dias > 30:
            alertas.append(
                f"Revisar cálculo temporal: posible artefacto por rango VADIGU "
                f"({tasa} int/día en {dias} días aparentes — el período puede incluir "
                f"múltiples episodios cortos, no una internación continua)"
            )
        # 🟡 Internación prolongada: outlier de duración, requiere verificación
        if dias > 365:
            alertas.append(f"Internación prolongada ({dias} días, {dias/365:.1f} años) — verificar completitud del registro")
        return ("🟢", alertas) if not alertas else ("🟡", alertas)

    st.subheader("Semáforo de calidad por HC")
    filas_sem = []
    for h in stale_rows:
        filas_sem.append({
            "Semáforo": "🔴",
            "Paciente": h["codigo_paciente"],
            "Archivo": h["archivo"][:45],
            "Estado": "Inconsistente",
            "Alertas": "Registro stale: excluido del conteo",
        })
    for c in casos:
        sem, alertas = _semaforo_hc(c, casos)
        filas_sem.append({
            "Semáforo": sem,
            "Paciente": c["codigo_paciente"],
            "Archivo": c["archivo"][:45],
            "Estado": "Consistente" if sem == "🟢" else ("Inconsistente" if sem == "🔴" else "Revisar"),
            "Alertas": " | ".join(alertas) if alertas else "—",
        })
    if filas_sem:
        st.dataframe(pd.DataFrame(filas_sem), width='stretch', hide_index=True)

    # --- Alertas metodológicas calibradas ---
    alertas_globales = []
    for c in casos:
        total = c["total_intervenciones"]
        dias  = c.get("dias_internacion") or 0
        raw   = raw_por_arch.get(c.get("archivo", ""), 0)
        tasa  = round(total / dias, 3) if dias else None
        pac   = c["codigo_paciente"]
        sem, sem_alertas = _semaforo_hc(c, casos)
        for a in sem_alertas:
            alertas_globales.append((sem, f"**{pac}** — {a}"))
    for h in stale_rows:
        alertas_globales.append(("🔴", f"**{h['codigo_paciente']}** — Registro stale excluido ({h['archivo'][:40]})."))

    st.subheader("Alertas metodológicas automáticas")
    if alertas_globales:
        for sem, texto in alertas_globales:
            if sem == "🔴":
                st.error(texto)
            else:
                st.warning(texto)
    else:
        st.success("No se detectaron alertas metodológicas en el dataset actual.")

    st.caption(
        "Criterios del semáforo: "
        "🔴 Inconsistente real (stale o duplicado exacto) · "
        "🟡 Revisar cálculo/metodología (artefacto temporal VADIGU, internación >365 días) · "
        "🟢 Consistente. "
        "No son criterios: psiquiatría=0, enfermería dominante, HC corta con tasa alta "
        "(son patrones estructurales del formato VADIGU)."
    )

elif modulo == "Informe":
    st.title("Informe Final - JSON")
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
