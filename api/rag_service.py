"""Recovery only over a reviewed, local corpus. No implicit model downloads."""
import hashlib
import io
import json
import os
from pathlib import Path
from threading import Lock
import pypdf
from fastapi import HTTPException
from api.runtime import ROOT

PROTOCOLS = Path(os.getenv('HCD_PROTOCOLS_DIR', str(ROOT / 'rag/protocolos'))).resolve()
MANIFEST = ROOT / 'rag/corpus_manifest.json'
DB = Path(os.getenv('HCD_RAG_DB_PATH', str(ROOT / 'rag/db-reviewed'))).resolve()
EMBEDDINGS = os.getenv('HCD_EMBEDDING_MODEL_PATH', '')
_lock = Lock()
_collection = None


def manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def reviewed(content):
    digest = hashlib.sha256(content).hexdigest()
    for item in manifest():
        if item['sha256'] == digest:
            return item
    raise HTTPException(403, 'Solo se admiten protocolos revisados incluidos en el manifiesto local.')


def chunks(content, suffix):
    try:
        if suffix == '.pdf':
            reader = pypdf.PdfReader(io.BytesIO(content))
            if len(reader.pages) > 500:
                raise ValueError()
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif suffix == '.txt':
            text = content.decode('utf-8')
        else:
            raise ValueError()
    except Exception:
        raise HTTPException(400, 'Documento no legible o formato no admitido.') from None
    result = [text[i:i+500] for i in range(0, len(text), 500) if text[i:i+500].strip()]
    if not result:
        raise HTTPException(422, 'Documento sin texto extraíble.')
    return result


def collection():
    global _collection
    with _lock:
        if _collection is None:
            if not EMBEDDINGS or not Path(EMBEDDINGS).is_dir():
                raise HTTPException(503, 'Embeddings locales no configurados. No se descargan automáticamente.')
            try:
                from sentence_transformers import SentenceTransformer
                import chromadb
                from chromadb.config import Settings
                from chromadb.api.types import EmbeddingFunction
                model = SentenceTransformer(EMBEDDINGS, local_files_only=True, device='cpu')
                class LocalEmbedding(EmbeddingFunction):
                    def __init__(self):
                        pass
                    def __call__(self, input):
                        return model.encode(input, normalize_embeddings=True).tolist()
                    @staticmethod
                    def name():
                        return 'hcd-local-reviewed'
                client = chromadb.PersistentClient(path=str(DB), settings=Settings(anonymized_telemetry=False))
                _collection = client.get_or_create_collection('protocolos_revisados_v1', embedding_function=LocalEmbedding())
            except Exception:
                raise HTTPException(503, 'Índice RAG o embeddings locales no disponibles.') from None
    return _collection


def index_reviewed(content, item):
    docs = chunks(content, Path(item['name']).suffix.lower())
    try:
        col = collection()
        # Content-addressed IDs prevent collisions and repeated-upload duplication.
        col.upsert(ids=[f"{item['sha256']}-{i}" for i in range(len(docs))], documents=docs,
                   metadatas=[{'fuente': item['name'], 'sha256': item['sha256']}] * len(docs))
        return len(docs)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'No se pudo actualizar el índice RAG.') from None


def retrieve(question, k):
    try:
        col = collection()
        count = col.count()
        if not count:
            raise HTTPException(409, 'El índice RAG está vacío; indexe protocolos revisados.')
        result = col.query(query_texts=[question], n_results=min(k, count),
                           where={'sha256': {'$in': [x['sha256'] for x in manifest()]}})
        documents = (result.get('documents') or [[]])[0]
        metadatas = (result.get('metadatas') or [[]])[0]
        ids = (result.get('ids') or [[]])[0]
        return [{'id': i, 'texto': d, 'fuente': m.get('fuente')} for i, d, m in zip(ids, documents, metadatas) if d and m]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Recuperación RAG no disponible.') from None
