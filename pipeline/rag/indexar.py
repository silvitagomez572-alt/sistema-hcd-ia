import chromadb
from chromadb.utils import embedding_functions
import pathlib
import pypdf

PROTOCOLOS_DIR = pathlib.Path("rag/protocolos")
DB_DIR = pathlib.Path("rag/db")

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path=str(DB_DIR))
collection = client.get_or_create_collection(
    name="protocolos_clinicos",
    embedding_function=ef
)

documentos = []
ids = []
metadatas = []

for archivo in PROTOCOLOS_DIR.iterdir():
    texto = ""
    if archivo.suffix == ".pdf":
        reader = pypdf.PdfReader(str(archivo))
        for page in reader.pages:
            texto += page.extract_text() or ""
    elif archivo.suffix == ".txt":
        texto = archivo.read_text(encoding="utf-8")
    
    if texto.strip():
        chunks = [texto[i:i+500] for i in range(0, len(texto), 500)]
        for j, chunk in enumerate(chunks):
            if chunk.strip():
                documentos.append(chunk)
                ids.append(f"{archivo.stem}_{j}")
                metadatas.append({"fuente": archivo.name})

collection.upsert(documents=documentos, ids=ids, metadatas=metadatas)
print(f"OK - {len(documentos)} chunks indexados de {PROTOCOLOS_DIR}")
