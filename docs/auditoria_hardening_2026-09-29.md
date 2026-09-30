# Auditoría previa al hardening — 2026-09-29

Auditoría estática completada antes de modificar código. Rama hardening-final ya existente. HEAD inicial 4508f53. Cambios previos preservados: api/main.py, api/tests/test_api.py, frontend/app.py, pipeline/censo/modulo_censo_mensual.py; informe previo y archivo 12.1.0 sin versionar.

Python 3.12.3; Docker 29.1.3; Compose v2.40.3; Ollama cliente 0.24.0 sin servidor activo. Docker socket denegado en sandbox. RAM 7,6 GiB; disco disponible 292 GiB. Existe .venv y modelo local en raíz; artifact documentado ausente. No se inspeccionan ni imprimen filas clínicas reales.

## Hallazgos y causas raíz

- P0: endpoints pseudonimizar devuelven texto_original/mapa_reemplazos con identidades; frontend ofrece el mapa.
- P0: rag/subir concatena nombre enviado al directorio; traversal, sin límite, acepta DOCX sin extractor y errores crudos. Indexación arbitraria permite PII en Chroma.
- P0: persistencia HCD conserva filename original; procesar-texto omite pseudonimización; IDs de intervención contienen fragmento de filename.
- P0: acceso sin autenticación, CORS comodín y operaciones destructivas abiertas; requiere perímetro local y bloqueo de borrados por defecto.
- P1: /rag/consulta y /llm/resumir ausentes; Ollama sin manejo HTTP/timeout; RAG falla sin colección o con colección vacía; carga de embeddings puede descargar recursos automáticamente.
- P1: DB relativa al cwd en API y absoluta en internaciones; init_db en import; tests usan DB real; rutas de modelo relativas y falta artifact en checkout limpio.
- P1: censo expone/persiste codigoHC, encabezados arbitrarios, excepciones; colisión de cargas por segundo; errores de persistencia silenciados; HTML móvil sin escaping.
- P1: Docker no copia pipeline/modelo/protocolos, puertos discrepantes, frontend usa localhost del contenedor, instala paquetes al iniciar, sin OCR/healthcheck/persistencia HCD.
- P1: Streamlit solicitudes sin timeout y fuera de try; muestra mapas y campos identificadores; ruta LAN hardcodeada.
- P2: dependencias sin versiones, pytest ausente, monolitos API (1176 líneas) y frontend (1738), sin logging estructurado, RAG sin evaluación, scripts con efectos al importar.

## Restricciones clínicas

README enumera tres tipos; REGLAS_CONTEO incluye más. Documentación reconoce artefactos de estada y subestimación psiquiátrica. Pseudonimizar firmas antes del clasificador puede impedir capa profesional. No se modifica regla, clasificación, fórmula ni esquema. Propuesta pendiente de aprobación: contrastar especificación con corpus revisado por profesionales, fijar ground truth y comparar conteos/áreas/estadas con validación independiente antes de cualquier cambio.

## Alcance de revisión

Árbol, archivos versionados, API, frontend, pipeline completo, tests, docs, CI, scripts e infraestructura revisados. Bases reales, secretos y archivos de pacientes no volcados. No se puede certificar ausencia de PII libre mediante regex; revisión hospitalaria y control de acceso siguen siendo necesarios.

## Seguimiento tras interrupción

Diagnóstico pip: .venv-hardening solo tenía pip 24.0; resolución DNS de pypi.org y files.pythonhosted.org falla con errno -2 dentro del sandbox, sin proxy ni índice personalizado en variables. HTTPS falla antes de TLS. Instalación reintentada con autorización de red y TLS intacto; acceso a PyPI confirmado. No se interpreta ausencia de distribuciones como incompatibilidad. Entorno .venv original preservado; baseline limpio en .venv-hardening.

codigoHC cumple tres funciones: reconstrucción de Documento en PDF, deduplicación de consolidado y búsqueda interna de HCD pendiente. La API móvil lo conserva en JSON porque solo excluye Paciente/Documento/nombre/dni; Streamlit lo muestra en auditoría de inconsistencias. No debe eliminarse en el parser ni antes de deduplicar. Plan: mantener valor solo en memoria de procesamiento, pseudónimo estable en persistencia/intercambio y vistas; probar equivalencia de deduplicación, y documentar límites de cruces con datos históricos. No migrar bases ni sobrescribir archivos existentes.

Revisión sintáctica AST: 14 archivos Python válidos. JSON maestro sintácticamente válido (ocho campos), contenido clínico no volcado. No hay scripts de entrenamiento versionados pese a documentación; reproducir el modelo requiere artifact validado externo. Identidad Git configurada por la usuaria; commits sin atribución a modelos.

## Baseline suplementario ejecutado

Entorno previo .venv: pytest 9.0.3, Python 3.12.3; 13 passed in 24.70s, 0 fallidos, 0 omitidos. Ejecución fuera del sandbox, cwd temporal, DB temporal vacía. Dentro del sandbox TestClient quedó bloqueado; reproducción mínima independiente de HCD obtuvo timeout en anyio.from_thread / selectors. No es un fallo del endpoint health. El test interrumpido no se cuenta como aprobado. Baseline limpio sigue instalándose.

Docker info fuera del sandbox confirmó motor 29.1.3. Compose config original ejecutado correctamente con advertencia version obsoleta; esto no valida build ni servicios.

Autorización de la usuaria: externalizar diccionario profesional conservando exactamente valores y comportamiento; guardar copia local excluida, plantilla sintética, error explícito si falta y prueba de equivalencia sin imprimir valores. No reescribir historial; la medida no elimina nombres de commits previos. Push autorizado solo a hardening-final después de revisión.

Baseline limpio: 13 passed, 1 warning in 9.79s; 0 fallidos/omitidos. Entorno Python 3.12.3 + pytest 9.1.1. Advertencia Starlette/httpx deprecado. Instalación completa sin desactivar TLS. Código aún sin correcciones durante esta medición.

## Cierre verificado

La condición inicial de Ollama inaccesible fue una observación dentro del sandbox; comprobación real posterior fuera del sandbox: tags HTTP 200 y generación breve HTTP 200 con tinyllama ya instalado. Sin descargas de modelos.

Fallos originales reproducidos con archivo sintético: traversal de rag/subir y filtración de un marcador privado de excepción. La comparación del diccionario confirmó igualdad exacta y comportamiento de todas sus entradas. Reglas/funciones clínicas seleccionadas conservadas por comparación AST. Predicción sintética con artifact existente en scikit-learn 1.6.1: sin advertencias de versión.

Pytest ampliado: primera pasada 40 aprobados; siguiente 62 aprobados y 1 fallo en Resumen HCs ante objeto vacío. Causa: acceso directo a resumen_ejecutivo. Corregido en frontend; final 63 aprobados, 0 fallidos, 0 omitidos. Cuatro warnings documentados (Starlette/httpx y optimizador sintético).

FastAPI HTTP real, SQLite tras reinicio e integrity_check, Streamlit health y Docker config/build/up con proceso sintético verificados. RAG real con Chroma y embeddings locales, en corpus/índice sintéticos. Benchmarks TF-IDF y SentenceTransformer+Chroma: Recall@1=1, MRR@1=1, Precision@1=1; a k=3 Recall=1, Precision=1/3, MRR=1, seis preguntas y seis documentos simples. No es evaluación clínica.

Instalación desde git archive del commit f1e0221800a41a8f36855f735bc8f7f19eb43111 en un venv nuevo: instalación y pip check correctos, 63 tests aprobados en 56.45 s. Sin privados copiados.

Siete archivos históricos con datos por paciente se retiraron únicamente del índice Git, conservados en disco y excluidos; no se reescribió historial. El escaneo de publicación distingue explícitamente la identidad de la autora solicitada. La falta de detección de nombres libres, salt/IDs heredados y controles hospitalarios faltantes permanecen documentados; no se declara producción hospitalaria.


Ampliación final de formatos: se reprodujo TypeError de pandas read_html(dtype=...) y dos fallos de endpoints de censo HTML/XLS. Se corrigió con StringIO y conversores por columna, conservando ceros iniciales; se agregaron cinco casos. Suite final: 68 passed, 5 warnings in 50.19s; 0 fallidos/omitidos. OCR real con Tesseract español e imagen generada sintética: palabra esperada detectada. No se usaron documentos de pacientes.

Cierre: copia limpia del commit 1588703ce6da742842fe6e856918d716aa78f5f0 instalada y verificada: pip check correcto; 68 tests aprobados, 0 fallidos, 0 omitidos, 5 advertencias, 73,30 s. Último build/up Docker del mismo código: health API/UI y procesamiento sintético HTTP 200. No se repitieron verificaciones aprobadas tras la interrupción.
