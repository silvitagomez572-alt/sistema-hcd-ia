FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa poppler-utils && rm -rf /var/lib/apt/lists/*
COPY requirements-core.lock .
RUN pip install --no-cache-dir -r requirements-core.lock && useradd --uid 10001 --create-home hcd && mkdir -p /app/data /app/uploads /app/rag/db-reviewed && chown -R hcd:hcd /app
COPY --chown=hcd:hcd api/*.py ./api/
COPY --chown=hcd:hcd frontend/ ./frontend/
COPY --chown=hcd:hcd pipeline/ ./pipeline/
COPY --chown=hcd:hcd rag/ ./rag/
COPY --chown=hcd:hcd .streamlit/ ./.streamlit/
USER hcd
EXPOSE 8000 8501
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
