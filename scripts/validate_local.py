"""Real local HTTP smoke validation, synthetic inputs and isolated persistence only."""
import argparse
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import requests

ROOT=Path(__file__).resolve().parents[1]

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def wait_http(url,process,auth=None):
    for _ in range(120):
        if process.poll() is not None:raise RuntimeError('service exited')
        try:
            result=requests.get(url,timeout=1,auth=auth)
            if result.status_code==200:return result
        except requests.RequestException:pass
        time.sleep(.25)
    raise TimeoutError('startup')

def validate():
    results={'fixture':'synthetic, actual HTTP and SQLite; synthetic trained sklearn model', 'checks':{}}
    with tempfile.TemporaryDirectory(prefix='hcd-http-validation-') as work:
        work=Path(work);env=os.environ.copy()
        env.update(HCD_DB_PATH=str(work/'test.db'),HCD_PROFESSIONALS_PATH=str(work/'professionals.json'),HCD_UPLOAD_DIR=str(work/'uploads'),HCD_MODEL_PATH=str(work/'synthetic.pkl'),HCD_API_PASSWORD='synthetic-validation',HCD_API_USER='operador',HCD_EMBEDDING_MODEL_PATH='',OLLAMA_MODEL='',STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
        (work/'professionals.json').write_text(json.dumps({'enfermeria':['profesional sintetico alfa']}))
        from sklearn.pipeline import make_pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        import joblib
        model=make_pipeline(TfidfVectorizer(),LogisticRegression(solver='liblinear',random_state=0))
        model.fit(['cuidados enfermeria','consulta psicologia'],['Enfermería','Psicología'])
        joblib.dump(model,work/'synthetic.pkl')
        api_port=port();front_port=port();base=f'http://127.0.0.1:{api_port}';env['HCD_API_URL']=base
        auth=('operador','synthetic-validation');processes=[]
        with (work/'services.log').open('w') as log:
            def start_api():
                proc=subprocess.Popen([sys.executable,'-m','uvicorn','api.main:app','--host','127.0.0.1','--port',str(api_port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
                processes.append(proc);wait_http(base+'/health',proc);return proc
            try:
                api=start_api()
                for path in ('/health','/docs','/mobile','/hcd/reportes','/hcd/reporte-total'):
                    r=requests.get(base+path,auth=auth,timeout=5);results['checks']['GET '+path]=r.status_code;assert r.status_code==200
                text='Paciente: Persona Sintetica DNI: 99999999\n01/09/2026 - 10:00 hs\nNota de enfermería\nControl de signos vitales y cuidados generales del turno.'
                r=requests.post(base+'/hcd/procesar-modelo',files={'archivo':('synthetic.txt',text.encode())},auth=auth,timeout=20)
                assert r.status_code==200 and r.json()['total_intervenciones']==1
                assert '99999999' not in r.text and 'Persona Sintetica' not in r.text
                results['checks']['POST /hcd/procesar-modelo']=200
                api.terminate();api.wait(timeout=10);api=start_api()
                rows=requests.get(base+'/hcd/reportes',auth=auth,timeout=5).json();assert len(rows)==1
                results['checks']['persistencia tras reinicio']=True
                with sqlite3.connect(work/'test.db') as con:assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                results['checks']['SQLite integrity_check']='ok'
                for endpoint,payload in [('/rag/consulta',{'pregunta':'protocolo sintético'}),('/llm/resumir',{'texto':'texto sintético'})]:
                    r=requests.post(base+endpoint,json=payload,auth=auth,timeout=5);assert r.status_code==503
                    results['checks'][endpoint+' dependencia no configurada']=503
                front=subprocess.Popen([sys.executable,'-m','streamlit','run','frontend/app.py','--server.address=127.0.0.1','--server.port='+str(front_port),'--server.headless=true','--browser.gatherUsageStats=false'],cwd=ROOT,env=env,stdout=log,stderr=log)
                processes.append(front);wait_http(f'http://127.0.0.1:{front_port}/_stcore/health',front)
                results['checks']['Streamlit HTTP health']=200
            finally:
                for proc in processes:
                    if proc.poll() is None:
                        proc.terminate()
                        try:proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=validate();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
