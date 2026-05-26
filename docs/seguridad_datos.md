# Política de datos y seguridad del repositorio

## Principio general

El repositorio público contiene únicamente código fuente, documentación técnica y estructura del proyecto. Ningún dato clínico real, identificatorio o derivado de historias clínicas se versiona en este repositorio.

## Archivos excluidos del versionado

### Historias clínicas originales
- Los archivos fuente del HMIS VADIGU (`.xls`, `.xlsx`) **no se versionan**.
- Deben mantenerse exclusivamente en el entorno local seguro de la institución.

### Base de datos clínica
- `hcs.db` **no se versiona** en el repositorio público.
- Debe generarse localmente a partir de datos pseudonimizados ejecutando el pipeline de procesamiento.
- Contiene texto extraído de historias clínicas; su exposición pública constituiría una violación de privacidad.

### Vectorstore ChromaDB
- El directorio `rag/db/` (ChromaDB) **no se versiona**.
- Debe regenerarse localmente ejecutando `pipeline/rag/indexar.py` sobre los protocolos disponibles en `rag/protocolos/`.

### Salidas con datos clínicos o de profesionales
- Los archivos en `outputs/` (`.csv`, `.xlsx`) **no se versionan**.
- Pueden contener métricas, validaciones o nombres de profesionales derivados del procesamiento clínico.

### Modelos serializados
- Los archivos `.pkl` **no se versionan**.
- El modelo `modelo_area_intervenciones.pkl` debe generarse localmente ejecutando el pipeline de entrenamiento en `pipeline/`.

## Pseudonimización

Los pacientes se referencian en toda la documentación y salidas del sistema como `PAC-{id:03d}` (ej: `PAC-001`, `PAC-002`). Ningún nombre real, DNI, teléfono ni dato identificatorio debe aparecer en archivos versionados.

## Qué sí contiene el repositorio público

- Código fuente: `api/`, `frontend/`, `pipeline/`
- Documentación técnica y clínica: `docs/`
- Protocolos clínicos de dominio público: `rag/protocolos/` (OPS, Ley 26657, publicaciones científicas)
- Infraestructura: `Dockerfile`, `docker-compose.yml`, `infra/`, `k8s/`
- Configuración: `requirements.txt`, `pytest.ini`, `.github/`

## Reproducibilidad

Para reproducir el entorno completo de desarrollo:

1. Clonar el repositorio.
2. Instalar dependencias: `pip install -r requirements.txt`.
3. Proveer los archivos `.xls` de VADIGU en entorno local (no incluidos por privacidad).
4. Ejecutar el pipeline para generar `hcs.db` y el modelo `.pkl`.
5. Indexar protocolos RAG: `python pipeline/rag/indexar.py`.
