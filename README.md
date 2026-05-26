# Sistema HCD IA — Análisis de Historias Clínicas en Salud Mental

## Trabajo Final Integrador — Infraestructura Tecnológica para Inteligencia Artificial

---

## Objetivo

Implementar un sistema de análisis automático de historias clínicas digitales (HCD) de pacientes internados en una unidad de salud mental, con procesamiento NLP local, clasificación por área profesional, detección de interconsultas y recuperación de información clínica aumentada (RAG).

---

## Autora

Lic. en Química Silvia Andrea Gómez Villagra

Trabajo Final Integrador — Inteligencia Artificial Generativa
Universidad Nacional de Luján (UNLu)

---

## Descripción del sistema

El sistema procesa información clínica proveniente del HMIS VADIGU (formatos XLS/HTML) y contempla una arquitectura multimodal para futuras entradas desde documentos PDF e imágenes escaneadas mediante OCR. Extrae bloques de texto clínico, los clasifica por área profesional mediante un clasificador híbrido (diccionario + keywords + TF-IDF/Logistic Regression), y produce métricas de actividad asistencial por paciente.

Incluye:

- API REST desarrollada con FastAPI (procesamiento NLP, métricas, interconsultas)
- Frontend Streamlit con 11 módulos clínicos
- Clasificador híbrido de 4 capas evaluado sobre historias clínicas reales pseudonimizadas.
- Módulo RAG (ChromaDB + SentenceTransformer) sobre protocolos clínicos
- LLM local (Gemma 2B vía Ollama) para resúmenes clínicos
- Auditoría clínica con semáforo de calidad por HC
- Pseudonimización: pacientes referenciados como `PAC-{id:03d}`

---

## Arquitectura

```
sistema-hcd-ia/
├── api/
│   ├── main.py                    # FastAPI — endpoints HCD, RAG, LLM, métricas
│   ├── hcd/data/                  # JSON maestro clínico
│   ├── rag/protocolos/            # Protocolos clínicos (copias indexadas)
│   └── tests/                     # Tests automáticos (en desarrollo)
├── frontend/
│   └── app.py                     # Streamlit — 11 módulos clínicos
├── pipeline/
│   ├── rag/indexar.py             # Indexación ChromaDB
│   ├── ocr/                       # OCR en desarrollo
│   ├── llm/                       # Scripts LLM local
│   └── pseudonimizacion/          # Utilidades de anonimización
├── training/                      # (implementado actualmente dentro de pipeline/)
├── artifacts/
│   ├── modelo_area_intervenciones.pkl   # Clasificador NLP serializado
│   └── outputs/                   # Validaciones y reportes exportados
├── rag/
│   ├── db/                        # ChromaDB vectorstore
│   └── protocolos/                # PDFs fuente (OPS, Ley 26657, Nature)
├── infra/terraform/               # Infraestructura como código (placeholder)
├── k8s/                           # Manifiestos Kubernetes (placeholder)
├── .github/workflows/             # CI/CD GitHub Actions
├── docs/                          # Documentación técnica y clínica
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── hcs.db                         # SQLite — historias clínicas procesadas
```

> **Nota:** `pipeline/` cumple el rol de `training/` en el patrón de referencia: contiene los scripts de entrenamiento del clasificador NLP, indexación RAG y utilidades. Los archivos no se mueven para no romper imports en producción.

---

## Endpoints principales (API — puerto 8001)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/hcd/procesar-modelo` | Procesar archivo HC (XLS/HTML VADIGU) |
| `GET` | `/hcd/reporte-total` | Métricas agregadas de todos los pacientes válidos |
| `GET` | `/hcd/reportes` | Listado de todos los registros en BD |
| `DELETE` | `/hcd/reportes/duplicados` | Eliminar duplicados exactos (mismo archivo) |
| `POST` | `/rag/consulta` | Consulta RAG sobre protocolos clínicos |
| `POST` | `/llm/resumir` | Resumen clínico vía LLM local |
| `GET` | `/health` | Estado del servicio |

Documentación interactiva: `http://localhost:8001/docs`

---

## Ejecución local

### Requisitos

```bash
pip install -r requirements.txt
```

Para el módulo LLM: Ollama en `localhost:11434` con modelo Gemma 2B.

```bash
ollama pull gemma:2b
```

### Backend (FastAPI)

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend (Streamlit)

```bash
streamlit run frontend/app.py --server.port 8502
```

### Docker

```bash
docker build -t hcd-ia .
docker run -p 8001:8001 hcd-ia
```

O con `docker-compose`:

```bash
docker compose up
```

### Tests

```bash
pytest api/tests -v
```

---

## Dataset actual (versión pre-entrega — 2026-05-25)

| Métrica | Valor |
|---------|-------|
| Pacientes únicos válidos | 4 |
| Intervenciones válidas totales | 1.231 |
| Días totales de internación | 905 |
| Tasa global intervenciones/día | 1.36 |
| ICs efectivas detectadas | 3 |
| Formato fuente | XLS/HTML exportado de VADIGU |

Ver `docs/version_estable_pre_entrega.md` para el detalle completo del dataset, semáforo de calidad por HC y limitaciones conocidas.

---

## Datos sensibles — advertencia

- Los archivos de HC originales (`.xls`) **no están versionados** en este repositorio.
- `hcs.db` **no se versiona** en el repositorio público; debe generarse localmente a partir de datos pseudonimizados ejecutando el pipeline de procesamiento.
- El vectorstore ChromaDB (`rag/db/`) **no se versiona**; debe regenerarse localmente con `pipeline/rag/indexar.py`.
- Los archivos de salida en `outputs/` **no se versionan**.
- La API **no devuelve `texto_extraido`** en ningún endpoint para proteger datos del paciente.
- Los pacientes se identifican únicamente como `PAC-{id:03d}` en toda la documentación y salidas del sistema.

Ver `docs/seguridad_datos.md` para la política completa de datos del repositorio.

---

## Estado actual del módulo RAG

El módulo RAG indexa protocolos clínicos en ChromaDB (`rag/db/`). Los protocolos fuente están en `rag/protocolos/`. La indexación se realiza con `pipeline/rag/indexar.py`. El módulo RAG se encuentra integrado a nivel de arquitectura e indexación documental. La validación clínica y evaluación sistemática continúan en desarrollo.

---

## Nota de entrega

Sistema desarrollado como Trabajo Final Integrador. La versión congelada para evaluación corresponde al commit documentado en `docs/version_estable_pre_entrega.md`. No se deben modificar los criterios clínicos, el clasificador NLP, REGLAS_CONTEO ni el esquema de base de datos sin actualizar ese documento.
