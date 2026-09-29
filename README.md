# Sistema HCD IA — entrega técnica 29/09/2026

**Autora:** Lic. en Química Silvia Andrea Gómez Villagra. Trabajo integrador, Universidad Nacional de Luján.

Procesamiento local de historias clínicas digitales de Salud Mental exportadas por HMIS/VADIGU, extracción estructurada de intervenciones, clasificación híbrida por área profesional y métricas asistenciales. Backend FastAPI, interfaz Streamlit, SQLite, OCR y módulos complementarios de censo, internaciones, RAG y Ollama.

[Informe técnico PDF](entrega/Informe_Tecnico_HCD_IA_Silvia_Gomez_Villagra.pdf) · [Fuente editable](entrega/Informe_Tecnico_HCD_IA_Silvia_Gomez_Villagra.md) · [Instalación, traslado y operación](docs/traslado_y_operacion.md)

## Alcance de la entrega

La versión corrige límites de carga, traversal de protocolos, respuestas de error, configuración, aislamiento de tests, persistencia y salidas de privacidad. No declara aptitud hospitalaria ni validación clínica por aprobar tests. Los resultados ejecutados y sus limitaciones están en el informe; las pruebas con mocks se identifican expresamente.

Las reglas clínicas, `REGLAS_CONTEO`, clasificación, cálculo de estadas e interconsultas se conservan. El diccionario de profesionales se externalizó con autorización, copia local previa y prueba de equivalencia. La versión pública contiene solo una plantilla sintética. Sin diccionario/modelo configurados, el procesamiento devuelve 503.

## Arquitectura y flujo

```text
Archivo VADIGU HTML/XLS o TXT
  -> validación y límite de entrada
  -> pseudonimización de identificadores detectables
  -> segmentación y reglas de conteo conservadas
  -> diccionario profesional + reglas de texto + TF-IDF/Logistic Regression
  -> métricas estructuradas y salida sin narrativa clínica
  -> SQLite local -> API -> Streamlit

Protocolos públicos revisados -> manifiesto SHA-256 -> ChromaDB local
  -> recuperación documental -> generación Ollama opcional y separada
```

El endpoint HCD admite XLS que contiene HTML (VADIGU); Excel binario/XLSX requiere conversión previa. El censo tiene sus propios lectores CSV, HTML/XLS, XLSX y PDF. OCR depende de Tesseract, idioma español y Poppler. PDF escaneado de censo no se convierte automáticamente con OCR.

## Inicio local

Probado en Python 3.12.3 / Linux x86_64. Para otra plataforma seguir el checklist de traslado.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip check
cp .env.example .env
# Configurar rutas locales, diccionario institucional y artifact validado.
uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

En otra terminal:

```bash
source .venv/bin/activate
streamlit run frontend/app.py --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false
```

API: `http://127.0.0.1:8000/docs`. UI: `http://127.0.0.1:8501`. No modificar ni sobrescribir un `.venv` o `.env` existente sin respaldarlo; durante el cierre se usó `.venv-hardening` para preservar el entorno previo.

```bash
pytest api/tests -v
python scripts/validate_local.py --output /tmp/validacion_hcd.json
```

Los tests aíslan SQLite, uploads y configuración privada. Las fixtures son sintéticas. El modelo institucional no está en Git y no hay un script de entrenamiento institucional versionado: su reproducibilidad científica completa sigue pendiente. `config/profesionales.example.json` no debe sustituir el diccionario validado real.

## Endpoints

| Método | Ruta | Comportamiento |
|---|---|---|
| GET | `/health`, `/docs` | Estado básico y contrato API |
| POST | `/hcd/procesar-modelo`, `/hcd/procesar-texto` | Pipeline clínico conservado, entradas validadas |
| GET | `/hcd/reportes`, `/hcd/reporte-total` | Reportes estructurados y agregados |
| POST | `/hcd/pseudonimizar` | Texto con identificadores detectados reemplazados, sin original ni mapa |
| POST | `/censos/upload` | Parseo y persistencia del censo protegido |
| GET/POST | `/mobile`, `/mobile/upload` | Formulario y carga de censo |
| POST | `/rag/consulta` | Solo recuperación documental |
| POST | `/rag/consultar` | Recuperación y generación local opcional |
| POST | `/llm/resumir`, `/llm/consultar` | Ollama local, errores controlados |

Errores: 400 archivo inválido; 413 exceso de tamaño; 422 entrada/no intervenciones reconocidas; 401 acceso no autorizado; 403 documento no revisado o borrado deshabilitado; 503 recurso local ausente; 502/504 respuesta inválida/timeout de Ollama. Las operaciones de borrado se deshabilitan por defecto.

## Discrepancias clínicas pendientes

La descripción histórica enumeraba tres tipos contables, mientras `REGLAS_CONTEO` incluye más marcadores. Las fechas de internación se infieren de registros y pueden tener artefactos; la atribución profesional y el criterio de confirmación de interconsultas requieren revisión clínica. Estos hallazgos no se corrigieron arbitrariamente. Se requiere corpus etiquetado independiente, revisión por profesionales, comparación de conteos/áreas/estadas y decisión institucional antes de cambiar las reglas.

La accuracy 92,98% que aparece como metadata histórica del modelo NO fue medida hoy. Los tests sintéticos verifican comportamiento de software, no sensibilidad, especificidad, validez clínica o representatividad poblacional.

## Privacidad y operación

Procesamiento local. No se versionan BD, uploads, archivos originales, diccionario institucional, modelos ni informes por paciente. El texto libre no se persiste en nuevos reportes NLP ni se devuelve como evidencia del clasificador. La pseudonimización por expresiones regulares tiene límites: nombres sin etiqueta y cuasiidentificadores pueden escapar; no garantiza anonimización. Las bases y archivos heredados no se limpiaron ni borraron automáticamente.

`codigoHC` se conserva durante el parseo y se transforma después en una clave estable de igualdad para persistencia/interfaz. Las pruebas verifican conservación de deduplicación. Los salt y hashes heredados requieren revisión de seguridad y migración controlada; conservar la configuración al trasladar datos.

La API puede usar HTTP Basic con contraseña local; sin contraseña se restringe a loopback. Para LAN se requieren TLS, control de acceso institucional y protección independiente de Streamlit. No exponer directamente a Internet. Los nombres retirados del código y los informes históricos permanecen en commits anteriores; no se reescribió el historial.

## Docker y módulos opcionales

```bash
# Antes: configurar HCD_API_PASSWORD y privados según docs/traslado_y_operacion.md
docker compose config --quiet
docker compose build
docker compose up -d
```

La imagen base incluye API/UI/OCR, sin RAG semántico ni modelos. El contexto Docker excluye privados. Los volúmenes SQLite/uploads persisten separados y los puertos se publican en loopback. No usar `down -v` con datos reales.

Para RAG local: instalar `requirements-rag.txt`, configurar un SentenceTransformer ya presente en disco y ejecutar `python -m pipeline.rag.indexar`. El índice revisado es independiente del vectorstore anterior. La evaluación sintética está en `rag/evaluation/`; mide recuperación por separado de generación. Ollama se configura solo con modelos ya instalados. La elección para la computadora nueva está pendiente de conocer RAM, CPU/GPU y SO; 1 TB no permite inferir capacidad de inferencia.
