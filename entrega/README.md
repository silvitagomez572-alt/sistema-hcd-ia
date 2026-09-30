# Entrega técnica — 29/09/2026

Autora: Lic. en Química Silvia Andrea Gómez Villagra.

El informe editable y su PDF se generan a partir de evidencia sintética y resultados de ejecución. Las métricas históricas documentadas en el repositorio no constituyen resultados obtenidos durante este cierre. Aprobar tests de software no equivale a validación clínica.

La copia institucional del diccionario de profesionales, los modelos entrenados, las bases y las historias clínicas no forman parte de la entrega pública. El historial previo no se reescribe.

Para regenerar el PDF en el entorno validado:

```bash
.venv-hardening/bin/python scripts/build_technical_report.py
```

Requiere ReportLab (incluido en el lock base) y las fuentes DejaVu Sans/Mono. En otra plataforma configurar `HCD_REPORT_FONT_DIR` con el directorio de esos archivos TTF. La fuente editable es Markdown; el PDF no depende de un servicio externo.

La tabla final de resultados distingue componentes reales de mocks. `pytest_resultados.xml` contiene 68 casos; las evidencias JSON adicionales corresponden a HTTP, Docker, RAG, OCR, Ollama, equivalencia, revisión de publicación e instalación limpia. La fuente de verdad de la versión publicada es el commit exacto del enlace GitHub suministrado al finalizar.
