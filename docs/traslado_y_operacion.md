# Traslado y operación local — versión de entrega 29/09/2026

Solo se conoce que la computadora nueva tendrá 1 TB de almacenamiento. RAM, CPU/GPU y sistema operativo están pendientes. La validación de hoy corresponde a Linux x86_64 y Python 3.12.3; no demuestra compatibilidad automática con otro sistema operativo.

## Instalación

```bash
git clone --branch hardening-final https://github.com/silvitagomez572-alt/sistema-hcd-ia.git
cd sistema-hcd-ia
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
cp .env.example .env
```

`requirements-core.lock` fija las versiones directas y transitivas verificadas del entorno base. `requirements-linux-py312-full.lock` registra el entorno completo instalado hoy, incluyendo RAG y bibliotecas CUDA. No instalar ese lock completo automáticamente en una máquina de sistema operativo o GPU desconocidos. `requirements-rag.txt` habilita dependencias opcionales: su resolución por plataforma debe validarse. PyTorch puede descargar bibliotecas CUDA grandes aun sin GPU; esto no descarga modelos LLM. El entorno base evita ese costo.

Editar `.env` localmente. Configurar contraseña propia si se accede desde Docker o red; la API sin contraseña solo admite clientes de loopback. HTTP Basic no sustituye TLS en LAN: mantener binding local o usar un proxy institucional con TLS y autenticación antes de exponer el servicio. Streamlit sigue requiriendo un perímetro de acceso propio antes de exposición de red.

En Linux, OCR requiere `tesseract-ocr`, datos de idioma `tesseract-ocr-spa` y `poppler-utils`. Docker los incluye. Verificar equivalentes en el sistema operativo nuevo. No ejecutar scripts de servicio systemd preexistentes sin revisar su configuración.

## Recursos privados imprescindibles

- Modelo NLP validado, configurado con `HCD_MODEL_PATH`. El artifact existente fue serializado con scikit-learn 1.6.1; esa versión se fija. Nunca cargar pickles de origen no confiable.
- Diccionario `HCD_PROFESSIONALS_PATH`: copiar la versión institucional privada a `.local/profesionales.json`. La copia conservada durante el cierre fue verificada por igualdad exacta y comportamiento de sus entradas, sin imprimir nombres.
- `config/profesionales.example.json` contiene solo valores sintéticos para explicar la estructura; NO reemplaza el diccionario institucional validado. El procesamiento responde 503 si falta el diccionario o el modelo. No se aplica un fallback silencioso.
- `PSEUDONYM_SALT`: transferir el valor institucional sin modificarlo. Cambiarlo cambia los pseudónimos y requiere un plan de migración y conciliación. La versión heredada tiene un salt público por defecto y hashes truncados; eso sigue siendo deuda de privacidad, no anonimización robusta. Para una instalación nueva configurar un valor aleatorio privado antes de cargar datos, y mantenerlo en backups privados.
- Historias clínicas y exportaciones de censo: transferir por canal institucional cifrado, fuera del repositorio. No arrastrar estos archivos a GitHub ni a un chat.

Los nombres retirados del código siguen en el historial previo. No se reescribió el historial y este cambio no constituye eliminación retrospectiva.

## Backup y restauración sin sobrescribir datos

Detener nuevas cargas mientras se copia el conjunto de archivos privados. La API `backup()` de SQLite produce una instantánea consistente incluso si hay conexiones abiertas; no copiar únicamente el `.db` con `cp` mientras haya escrituras o WAL activos. No ejecutar borrados ni migraciones durante el traslado.

Elegir un destino NUEVO fuera del repositorio y en almacenamiento cifrado:

```bash
python scripts/private_backup.py backup \
  --database /ruta/privada/hcs.db \
  --destination /ruta/privada/backup_2026_09_29 \
  --private /ruta/privada/profesionales.json \
  --private /ruta/privada/modelo_area_intervenciones.pkl \
  --private /ruta/privada/.env
```

El script exige destinos inexistentes, usa permisos privados, verifica integridad SQLite y registra checksums. No cifra por sí mismo. La copia incluye archivos privados explícitos; repetir `--private` para cada archivo adicional. Para muchos censos/uploads, copiar además sus directorios mediante herramienta institucional cifrada preservando permisos y un inventario de hashes, con el servicio detenido. El vectorstore puede regenerarse desde los protocolos aprobados y el modelo local de embeddings; no es obligatorio trasladarlo.

En el equipo nuevo:

```bash
python scripts/private_backup.py restore \
  --source /ruta/privada/backup_2026_09_29 \
  --destination /ruta/privada/restauracion_prueba
```

La restauración conserva `database.sqlite3`, `asset_000`, etc. El manifiesto privado indica el nombre original de cada asset. Mapearlos manualmente a las rutas de `.env`, sin sobrescribir la instalación anterior. No publicar el manifiesto, los assets ni los backups. Probar primero esta copia; conservar el origen como rollback. La prueba automatizada de backup/restauración usa una tabla sintética, no la base hospitalaria.

## Inicio

Desde la raíz del repositorio y con el entorno activado:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

En otra terminal, mismo entorno y directorio:

```bash
streamlit run frontend/app.py --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false
```

Visitar `http://127.0.0.1:8000/health`, `http://127.0.0.1:8000/docs` y `http://127.0.0.1:8501`. Los access logs se deshabilitan para no registrar parámetros o identificadores en URLs. El logger de aplicación registra operación, estado y request ID sin body ni query string. El procesamiento sigue siendo local.

```bash
pytest api/tests -v
python scripts/validate_local.py --output /tmp/validacion_hcd.json
```

Estas verificaciones crean recursos sintéticos aislados. No son validación clínica ni evaluación del modelo institucional.

## Docker

Configurar `HCD_API_PASSWORD` en `.env`. Copiar el artifact institucional a `.local/modelo_area_intervenciones.pkl`, sin mover ni borrar la copia original; el diccionario ya debe estar en `.local/profesionales.json`. El usuario interno tiene UID 10001: montar solo los archivos necesarios con ACL de lectura para ese UID, evitando hacerlos públicos. Los directorios de datos/uploads usan volúmenes separados.

```bash
docker compose config --quiet
docker compose build
docker compose up -d
```

Los puertos se publican en loopback. El contenedor base incluye HCD, censo, internaciones, UI y OCR; RAG semántico requiere imagen con dependencias opcionales y montaje de embeddings locales, no está incluido en el contenedor base. El perfil `llm` es opcional y no descarga modelos; no activarlo automáticamente en hardware desconocido. Los volúmenes Docker existentes no se migran automáticamente al clonar Git. No usar `docker compose down -v` sobre datos institucionales.

## RAG y Ollama

La indexación usa un corpus público revisado identificado por SHA-256 (`rag/corpus_manifest.json`). Nuevos protocolos requieren revisión humana de privacidad y procedencia antes de actualizar el manifiesto. Se usa un índice nuevo (`rag/db-reviewed`) para no confiar ciegamente en cargas previas; el vectorstore anterior no se borra. Los embeddings deben estar disponibles localmente:

```bash
pip install -r requirements-rag.txt
# Configurar HCD_EMBEDDING_MODEL_PATH en .env con un directorio local completo.
python -m pipeline.rag.indexar
python -m rag.evaluation.evaluate --output /tmp/recuperacion_tfidf.json
python -m rag.evaluation.evaluate --backend sentence-transformer \
  --model-path /ruta/local/embeddings --output /tmp/recuperacion_semantica.json
```

`/rag/consulta` realiza recuperación sin generación; `/rag/consultar` añade generación Ollama. El benchmark sintético no mide calidad clínica, grounding ni seguridad de recomendaciones. Cada pregunta tiene una etiqueta documental relevante; Recall@k=aciertos/relevantes, Precision@k=aciertos/k, MRR@k=promedio del inverso del primer rango relevante (0 si no aparece).

```bash
ollama serve
curl http://localhost:11434/api/tags
ollama list
```

Si ya hay un servicio activo, no iniciar un segundo. Elegir `OLLAMA_MODEL` SOLO después de conocer RAM, CPU/GPU y modelos locales. No se descargó ningún LLM durante el cierre. La disponibilidad de 1 TB no determina la capacidad de inferencia. Revisar RAM libre y espacio antes de instalar modelos; probar latencia, memoria máxima y concurrencia con carga sintética.

## Checklist de aceptación del equipo nuevo

1. Registrar SO, arquitectura, CPU, RAM, GPU/controladores y almacenamiento libre; cifrado de disco y usuarios autorizados.
2. Crear entorno nuevo, instalar lock aplicable y ejecutar `pip check`; registrar cualquier resolución diferente.
3. Verificar checksums de archivos privados y `integrity_check` de SQLite restaurada, preservando origen.
4. Iniciar API y UI en loopback; comprobar health/docs y acceso autorizado.
5. Ejecutar tests y `validate_local.py` con recursos sintéticos; confirmar procesamiento, reinicio y persistencia.
6. Verificar equivalencia institucional del diccionario/artifact por canal local, sin exponer valores ni mezclar pruebas con datos reales.
7. Comprobar API caída, respuesta vacía y métricas de UI frente a API; verificar OCR y formatos de exportación realmente utilizados.
8. Si hay embeddings: regenerar índice revisado y repetir benchmark, registrando versiones/modelo/revisión.
9. Si hay Ollama: comprobar tags y generación sintética, consumo máximo y tiempos; calidad clínica queda pendiente.
10. Antes de uso hospitalario: autenticación/roles, TLS, auditoría persistente, backup cifrado probado, política de retención, revisión de reidentificación, validación clínica independiente y aprobación institucional.
