"""Checks an already installed local model with a synthetic, nonclinical prompt."""
import json
from pathlib import Path
import httpx

if __name__=='__main__':
    result={'downloaded_models':False}
    try:
        with httpx.Client(base_url='http://localhost:11434',timeout=90,trust_env=False) as client:
            tags=client.get('/api/tags');tags.raise_for_status()
            available={x['name'] for x in tags.json().get('models',[])}
            result['tags_http']=tags.status_code
            if 'tinyllama:latest' not in available:
                result['generation']='blocked: test model not installed'
            else:
                response=client.post('/api/generate',json={'model':'tinyllama:latest','prompt':'Responde brevemente: una prueba de software usa datos sintéticos.','stream':False,'options':{'num_predict':24,'temperature':0},'keep_alive':0})
                response.raise_for_status()
                result.update(generation_http=response.status_code,nonempty_response=bool(response.json().get('response')),model='tinyllama:latest',clinical_quality_evaluated=False)
    except Exception as exc:
        result['blocked']=type(exc).__name__
    Path('entrega/validacion_ollama.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
