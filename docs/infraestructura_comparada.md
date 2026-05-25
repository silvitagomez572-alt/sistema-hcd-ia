# Infraestructura comparada — HCD IA vs proyecto de referencia

**Fecha:** 2026-05-25
**Referencia:** `hospital-triage-ia` (proyecto base aprobado)
**Sistema:** `sistema-hcd-ia` (este proyecto)

---

## Tabla de comparación

| Componente | Proyecto triaje | Sistema HCD IA | Estado |
|------------|-----------------|----------------|--------|
| `api/` | ✅ FastAPI endpoints REST, modelo, schemas | ✅ FastAPI — 655 líneas, endpoints HCD/RAG/LLM/métricas | ✅ Equivalente |
| `api/tests/` | ✅ Tests con pytest + httpx | ⚠️ `api/tests/test_api.py` creado (tests de humo) | ⚠️ Parcial |
| `frontend/` | ✅ Streamlit | ✅ Streamlit — 11 módulos clínicos, ~750 líneas | ✅ Equivalente |
| `training/` | ✅ Scripts de entrenamiento del modelo | ⚠️ `pipeline/` — scripts NLP, RAG, OCR, pseudonimización | ⚠️ Análogo (nombre diferente) |
| `artifacts/` | ✅ Métricas, datasets sintéticos, modelos | ⚠️ `artifacts/README.md` — modelos y outputs distribuidos | ⚠️ Parcial |
| `infra/terraform/` | ✅ Terraform completo (6 archivos .tf) | ⚠️ `infra/terraform/README.md` — placeholder conceptual | ⚠️ Placeholder |
| `k8s/` | ✅ Deployment + HPA reales | ⚠️ `k8s/README.md` — arquitectura prevista conceptual | ⚠️ Placeholder |
| `.github/workflows/` | ✅ `tests.yml` con pytest en CI | ✅ `tests.yml` creado — equivalente | ✅ Equivalente |
| `Dockerfile` | ✅ Imagen de la API | ✅ Imagen del backend FastAPI | ✅ Equivalente |
| `docker-compose.yml` | ❌ No presente | ✅ Presente (backend + frontend) | ✅ Extendido |
| `requirements.txt` | ✅ | ✅ | ✅ Equivalente |
| `pytest.ini` | ✅ | ✅ Creado — `testpaths = api/tests` | ✅ Equivalente |
| `README.md` | ✅ | ✅ Creado — objetivo, arquitectura, endpoints, datos sensibles | ✅ Equivalente |
| `docs/` | ❌ No presente | ✅ Presente — 4 documentos técnico-clínicos | ✅ Extendido |

---

## Diferencias estructurales justificadas

### `pipeline/` en lugar de `training/`

El proyecto de referencia tiene `training/` con dos scripts de entrenamiento del modelo de ML. Este sistema tiene `pipeline/` con cuatro subdirectorios:

| Subdirectorio | Propósito |
|---------------|-----------|
| `pipeline/rag/indexar.py` | Indexación de protocolos en ChromaDB |
| `pipeline/ocr/` | OCR de imágenes (en desarrollo) |
| `pipeline/llm/` | Scripts LLM local |
| `pipeline/pseudonimizacion/` | Utilidades de anonimización |

El nombre `pipeline/` refleja mejor la naturaleza del sistema (pipeline NLP complejo vs. script de entrenamiento puntual). **No se renombra** para evitar romper imports.

### `artifacts/` distribuido

El proyecto de referencia concentra artefactos en `artifacts/`. En este sistema:
- `modelo_area_intervenciones.pkl` está en la raíz (cargado por `api/main.py` con ruta relativa)
- `outputs/` contiene validaciones exportadas
- `reports/` está vacío

Se documenta en `artifacts/README.md`. El modelo no se mueve para no romper el import en producción.

### `docs/` adicional

El proyecto de referencia no tiene `docs/`. Este sistema tiene documentación técnica extensa (validación clínica, calibración, versión estable, infraestructura comparada) como parte del TFI.

### `rag/` adicional

Componente sin equivalente en el proyecto de referencia. ChromaDB vectorstore con protocolos clínicos indexados. Propio de la arquitectura RAG del sistema HCD.

### `docker-compose.yml` adicional

El proyecto de referencia no lo tiene; este sistema orquesta backend (8001) y frontend (8502) juntos.

---

## Resumen ejecutivo

El sistema HCD IA cubre todos los componentes del patrón de referencia. Los elementos marcados como placeholder (`infra/terraform/`, `k8s/`) siguen el patrón estructural sin implementar despliegue real, consistente con el alcance del TFI. Los tests automáticos están creados como tests de humo; la cobertura es básica y extensible.

---

*Documento generado para alineación académica con el proyecto base aprobado.*
*No modificar la estructura de archivos existentes sin actualizar esta tabla.*
