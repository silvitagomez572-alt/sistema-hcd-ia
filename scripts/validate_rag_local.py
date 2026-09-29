"""Actual Chroma + local SentenceTransformer + API, synthetic reviewed corpus."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model-path',required=True);args=parser.parse_args()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    with tempfile.TemporaryDirectory(prefix='hcd-rag-api-') as work:
        work=Path(work);os.environ['HCD_DB_PATH']=str(work/'test.db');os.environ['HCD_API_PASSWORD']=''
        from api import main,rag_service
        from fastapi.testclient import TestClient
        texts=[('backup.txt','El respaldo SQLite usa backup y verifica integrity_check antes de restaurar.'),('ollama.txt','Ollama serve inicia el servidor local. api/tags enumera modelos instalados.')]
        manifest=[{'name':name,'sha256':hashlib.sha256(text.encode()).hexdigest()} for name,text in texts]
        rag_service.MANIFEST=work/'manifest.json';rag_service.MANIFEST.write_text(json.dumps(manifest))
        rag_service.DB=work/'chroma';rag_service.EMBEDDINGS=args.model_path
        with TestClient(main.app) as client:
            for name,text in texts:
                response=client.post('/rag/subir',files={'archivo':(name,text.encode())})
                assert response.status_code==200, response.json()
            response=client.post('/rag/consulta',json={'pregunta':'¿Cómo respaldar SQLite y verificar la integridad?','k':1})
            assert response.status_code==200, response.json()
            assert response.json()['documentos'][0]['fuente']=='backup.txt'
            assert response.json()['generacion_llm'] is False
            result={'actual_chroma':True,'actual_local_embeddings':True,'synthetic_corpus':True,'upload_http':200,'retrieval_http':200,'expected_top_document':True,'llm_called':False,'downloaded_models':False}
        Path('entrega/validacion_rag_api.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
