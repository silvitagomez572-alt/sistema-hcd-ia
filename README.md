# Sistema Multimodal basado en Inteligencia Artificial Generativa para la Extracción Estructurada de Intervenciones Clínicas a partir de Historias Clínicas Digitales

## Autora

Lic. en Química Silvia Andrea Gómez Villagra
Trabajo Práctico Integrador – Materia 4
Universidad Nacional de Luján (UNLu)

---

## Objetivo

Desarrollar un sistema de procesamiento automatizado de historias clínicas digitales (HCD) de pacientes internados en una unidad de salud mental, con extracción estructurada de intervenciones clínicas, clasificación por área profesional, detección de interconsultas y generación de métricas de actividad asistencial. El sistema opera localmente sobre datos pseudonimizados, sin dependencia de servicios externos.

---

## Descripción del sistema

El sistema procesa información clínica proveniente del HMIS VADIGU (formatos XLS/HTML), archivos PDF y documentos de texto. Extrae bloques de texto clínico, los clasifica por área profesional mediante un clasificador híbrido (diccionarios clínicos + keywords + reglas + TF-IDF/Logistic Regression), y produce métricas de actividad asistencial por paciente.

Incluye:

- API REST desarrollada con FastAPI (procesamiento NLP, métricas, interconsultas, censo)
- Frontend Streamlit con módulos clínicos y de gestión operacional
- Clasificador híbrido de 4 capas evaluado sobre historias clínicas reales pseudonimizadas
- Módulo RAG (ChromaDB + SentenceTransformer) sobre protocolos clínicos
- LLM local mediante Ollama, configurable según hardware disponible, para resúmenes clínicos
- Módulo OCR integrado en pipeline para procesamiento de imágenes escaneadas
- Auditoría clínica con semáforo de calidad por HC
- Pseudonimización: pacientes referenciados como `PAC-{id:03d}`

---

## Criterios de conteo de intervenciones clínicas

Se contabilizan como intervenciones clínicas únicamente los bloques que corresponden a:

- Nota de enfermería
- Evolución clínica
- Seguimiento

Se excluyen del conteo:

- Encabezados y datos administrativos del paciente
- Tablas de medicación e indicaciones
- Bloques sin texto clínico sustantivo (texto no clínico)

Este criterio fue establecido en consenso con el servicio y se aplica de forma uniforme a todos los registros procesados.

---

## Clasificador híbrido de área profesional

El clasificador asigna cada bloque de texto a un área profesional mediante cuatro capas aplicadas en cascada:

1. **Diccionarios clínicos:** términos específicos por área (enfermería, psicología, terapia ocupacional, trabajo social, psiquiatría, acompañante terapéutico) curados manualmente a partir del corpus real.
2. **Keywords y contexto:** patrones contextuales que resuelven ambigüedades entre áreas con vocabulario compartido.
3. **Reglas clínicas:** condiciones estructurales del bloque (posición en el documento, longitud mínima, formato de encabezado).
4. **TF-IDF + Regresión Logística:** clasificador estadístico entrenado sobre intervenciones pseudonimizadas reales, utilizado cuando las capas anteriores no resuelven la asignación.

El modelo entrenado se serializa en `modelo_area_intervenciones.pkl`.

---

## Módulos de Censo e Internaciones — justificación de incorporación

El objetivo central del proyecto es la extracción estructurada de intervenciones clínicas a partir de HCDs. Sin embargo, para interpretar los indicadores de actividad resultantes se requiere contextualización poblacional: pacientes atendidos durante el mes, ingresos, egresos, reingresos, estadas y ocupación de camas.

Sin esa información, indicadores como tasa de intervenciones por día o giro de camas carecen de denominador poblacional verificable.

Por esta razón, los módulos de Censo Mensual e Internaciones se incorporaron como **fuentes de datos operacionales complementarias**, no como objetivo principal del proyecto. Su función es proveer contexto de validación y conciliación para los indicadores clínicos extraídos de las HCDs.

---

## Módulo Censo Mensual

Lee censos exportados del HMIS VADIGU en formato CSV, Excel (XLS/XLSX), HTML y PDF, consolida los pacientes únicos del mes y genera estadísticas de ocupación en Salud Mental.

- **Formatos soportados:** CSV, Excel (XLS/XLSX), HTML, PDF
- **Consolidación:** deduplica pacientes por `codigoHC` y por DNI (campo `Documento`), conservando el registro con mayor estadía
- **Estadísticas:** total de pacientes SM únicos, pico de camas ocupadas, porcentaje de ocupación, promedio de estada y giro de camas
- **Trazabilidad:** cruza el censo mensual con las HCs ya procesadas en la BD para identificar qué pacientes aún no fueron analizados

---

## Carga de censos desde dispositivos móviles

Se incorporó una ruta de carga por formulario HTML nativo en FastAPI (`/mobile`) para facilitar la subida de archivos de censo desde dispositivos Android dentro de la red local. La carga opera sin JavaScript y no requiere que Streamlit esté activo en el dispositivo. Los datos procesados quedan disponibles para su carga posterior desde el módulo Censo Mensual.

---

## Arquitectura

```
sistema-hcd-ia/
├── api/
│   ├── main.py                    # FastAPI — endpoints HCD, RAG, LLM, censo, métricas
│   ├── hcd/data/                  # JSON maestro clínico
│   └── rag/protocolos/            # Protocolos clínicos (copias indexadas)
├── frontend/
│   └── app.py                     # Streamlit — módulos clínicos y operacionales
├── pipeline/
│   ├── censo/                     # Parseo y consolidación de censos VADIGU
│   ├── rag/indexar.py             # Indexación ChromaDB
│   ├── ocr/                       # OCR sobre imágenes y PDF escaneados
│   ├── llm/                       # Scripts LLM local
│   └── pseudonimizacion/          # Utilidades de anonimización
├── artifacts/
│   └── modelo_area_intervenciones.pkl   # Clasificador NLP serializado
├── outputs/                       # Validaciones y reportes (no versionados)
├── rag/
│   ├── db/                        # ChromaDB vectorstore (no versionado)
│   └── protocolos/                # PDFs fuente (OPS, Ley 26657, Nature)
├── uploads/censos/                # Archivos de censo subidos desde móvil (no versionados)
├── docs/                          # Documentación técnica y clínica
├── infra/terraform/               # Infraestructura como código
├── k8s/                           # Manifiestos Kubernetes
├── .github/workflows/             # CI/CD GitHub Actions
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── hcs.db                         # SQLite — historias clínicas procesadas (no versionado)
```

> `pipeline/` contiene los scripts de entrenamiento del clasificador NLP, indexación RAG y utilidades de procesamiento. Los archivos no se reorganizan para no romper imports en producción.

---

## Endpoints principales (API — puerto 8000)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/hcd/procesar-modelo` | Procesar archivo HC (XLS/HTML VADIGU) |
| `GET`  | `/hcd/reporte-total` | Métricas agregadas de todos los pacientes válidos |
| `GET`  | `/hcd/reportes` | Listado de todos los registros en BD |
| `DELETE` | `/hcd/reportes/duplicados` | Eliminar duplicados exactos (mismo archivo) |
| `POST` | `/censos/upload` | Cargar archivo de censo (responde JSON) |
| `POST` | `/mobile/upload` | Cargar censo desde formulario móvil (responde HTML) |
| `POST` | `/rag/consulta` | Consulta RAG sobre protocolos clínicos |
| `POST` | `/llm/resumir` | Resumen clínico vía LLM local |
| `GET`  | `/mobile` | Página de carga de censo para dispositivos móviles |
| `GET`  | `/health` | Estado del servicio |

Documentación interactiva: `http://localhost:8000/docs`

---

## Ejecución local

### Requisitos

```bash
pip install -r requirements.txt
```

Para el módulo LLM: Ollama instalado y en ejecución en `localhost:11434`. El modelo utilizable depende del hardware disponible; se recomienda al menos 8 GB de RAM para modelos de 2B–7B parámetros.

### Backend (FastAPI)

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (Streamlit)

```bash
streamlit run frontend/app.py
```

### Docker

```bash
docker build -t hcd-ia .
docker run -p 8000:8000 hcd-ia
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

## Dataset actual (2026-05-25)

| Métrica | Valor |
|---------|-------|
| Pacientes únicos válidos | 4 |
| Intervenciones válidas totales | 1.231 |
| Días totales de internación | 905 |
| Tasa global intervenciones/día | 1,36 |
| ICs efectivas detectadas | 3 |
| Formato fuente | XLS/HTML exportado de VADIGU |

Ver `docs/version_estable_pre_entrega.md` para el detalle completo del dataset, semáforo de calidad por HC y limitaciones conocidas.

---

## Privacidad y datos sensibles

- Los archivos de HC originales (`.xls`) **no están versionados** en este repositorio.
- `hcs.db` **no se versiona**; debe generarse localmente a partir de datos pseudonimizados ejecutando el pipeline de procesamiento.
- El vectorstore ChromaDB (`rag/db/`) **no se versiona**; debe regenerarse localmente con `pipeline/rag/indexar.py`.
- Los archivos en `outputs/` y `uploads/` **no se versionan**.
- La API **no devuelve `texto_extraido`** en ningún endpoint público.
- Los pacientes se identifican únicamente como `PAC-{id:03d}` en toda la documentación y salidas del sistema.
- Los campos `Paciente` (nombre) y `Documento` (DNI) se utilizan exclusivamente para deduplicación dentro de la sesión activa; **no se persisten en base de datos ni se exportan** en ningún reporte.

Ver `docs/seguridad_datos.md` para la política completa de datos del repositorio.

---

## Estado actual del módulo RAG

El módulo RAG indexa protocolos clínicos en ChromaDB (`rag/db/`). Los protocolos fuente están en `rag/protocolos/`. La indexación se realiza con `pipeline/rag/indexar.py`. El módulo se encuentra integrado a nivel de arquitectura e indexación documental. La validación clínica y la evaluación sistemática de recuperación continúan en desarrollo.

---

## Nota de entrega

Sistema desarrollado como Trabajo Práctico Integrador – Materia 4. La versión congelada para evaluación corresponde al commit documentado en `docs/version_estable_pre_entrega.md`. No se deben modificar los criterios clínicos, el clasificador NLP, `REGLAS_CONTEO` ni el esquema de base de datos sin actualizar ese documento.
