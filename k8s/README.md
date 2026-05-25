# k8s/ — Arquitectura de despliegue prevista

Este directorio documenta la arquitectura Kubernetes prevista para el sistema HCD IA.
**No contiene manifests ejecutables.** Es documentación académica de referencia.

---

## Componentes esperados

El sistema se compone de cuatro servicios principales:

### 1. `hcd-api` — Backend FastAPI
- Imagen basada en `python:3.12-slim`
- Puerto: 8001
- Responsabilidades: procesamiento NLP de HCs, endpoints de métricas, RAG, LLM proxy
- Requiere acceso al volumen con `hcs.db` y `modelo_area_intervenciones.pkl`

### 2. `hcd-frontend` — Streamlit
- Imagen basada en `python:3.12-slim`
- Puerto: 8502
- Responsabilidades: interfaz de usuario, visualizaciones Altair, módulos clínicos
- Se comunica con `hcd-api` vía HTTP interno

### 3. `rag-store` — ChromaDB
- Vectorstore para recuperación de protocolos clínicos
- Persiste en volumen `rag/db/`
- Accedido directamente por `hcd-api` en esta versión (sin servicio separado)

### 4. `llm-local` — Ollama / Gemma 2B
- LLM local para resúmenes clínicos
- Puerto: 11434
- En la versión actual se asume Ollama corriendo en el nodo host
- En despliegue productivo requeriría un pod dedicado con GPU o CPU suficiente

---

## Arquitectura prevista (conceptual)

```
                    ┌─────────────────┐
                    │   Ingress / LB  │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐         ┌──────────▼──────────┐
     │  hcd-frontend   │         │     hcd-api          │
     │  (Streamlit)    │◄───────►│     (FastAPI)        │
     │  :8502          │  HTTP   │     :8001            │
     └─────────────────┘         └──────┬───────┬───────┘
                                        │       │
                               ┌────────▼─┐  ┌──▼──────────┐
                               │ rag/db   │  │ llm-local   │
                               │(ChromaDB)│  │ (Ollama)    │
                               └──────────┘  └─────────────┘
```

---

## Consideraciones para despliegue real

- **Datos sensibles:** `hcs.db` contiene texto clínico extraído — requiere PVC con acceso restringido y no debe exponerse públicamente.
- **Modelo NLP:** `modelo_area_intervenciones.pkl` debe montarse como volumen o incluirse en la imagen con cuidado de versionar el modelo junto al código que lo usa.
- **LLM:** Gemma 2B requiere ~4GB RAM. En producción hospitalaria se recomendaría un nodo con GPU dedicada o un servicio LLM externo con garantías de privacidad de datos.
- **Autenticación:** la versión actual no implementa autenticación en los endpoints — requerido antes de cualquier despliegue con datos reales de pacientes.

---

## Estado

Placeholder académico. Sistema ejecutándose en localhost para la versión pre-entrega 2026-05-25.
Ver `docs/version_estable_pre_entrega.md` para el estado actual del sistema.
