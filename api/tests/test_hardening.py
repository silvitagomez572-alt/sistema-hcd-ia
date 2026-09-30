import json
import sqlite3
import asyncio
import hashlib
import io
import pytest
import httpx
import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient
from api import main, runtime, rag_service, llm

client = TestClient(main.app, raise_server_exceptions=False)
TEXT = 'Paciente: Persona Sintetica DNI: 99999999\n01/09/2026 - 10:00 hs\nNota de enfermería\nControl de signos vitales y cuidados generales del turno.'

def test_docs_and_empty_database():
    assert client.get('/docs').status_code == 200
    assert client.get('/hcd/reportes').json() == []
    assert client.get('/hcd/reporte-total').json()['resumen_ejecutivo']['total_pacientes'] == 0
    assert client.get('/hcd/summary').status_code == 404

def test_processing_persistence_and_dedup(synthetic_model):
    for _ in range(2):
        response = client.post('/hcd/procesar-modelo', files={'archivo': ('persona_99999999.txt', TEXT.encode(), 'text/plain')})
        assert response.status_code == 200, response.status_code
        assert response.json()['total_intervenciones'] == 1
        assert sum(response.json()['intervenciones_por_area'].values()) == 1
        assert '99999999' not in response.text and 'Persona Sintetica' not in response.text
    total = client.get('/hcd/reporte-total').json()['resumen_ejecutivo']
    assert total['total_pacientes'] == 1 and total['total_intervenciones'] == 1
    with sqlite3.connect(main.DB_PATH) as con:
        rows = con.execute('select archivo,resumen,texto_extraido from hcs_procesadas').fetchall()
    assert len(rows) == 2 and all(row[2] == '' for row in rows)
    assert '99999999' not in str(rows) and 'Persona Sintetica' not in str(rows)
    assert client.delete('/hcd/reportes/limpiar').status_code == 403

@pytest.mark.parametrize('name,content', [('a.exe',b'bad'),('a.xlsx',b'PKbad'),('a.txt',b''),('a.xls',b'\x00bad'),('../x.txt',b'bad')])
def test_invalid_files(name,content):
    assert client.post('/hcd/procesar-modelo',files={'archivo':(name,content)}).status_code == 400

@pytest.mark.parametrize('name', ['../escape.txt', '/tmp/escape.txt', '..\\escape.txt', 'a:b.txt'])
def test_rag_traversal_rejected(name,tmp_path,monkeypatch):
    monkeypatch.setattr(rag_service,'PROTOCOLS',tmp_path/'protocols')
    response=client.post('/rag/subir',files={'archivo':(name,b'synthetic text')})
    assert response.status_code == 400
    assert not list(tmp_path.glob('*.txt'))

def test_unreviewed_rag_rejected():
    response=client.post('/rag/subir',files={'archivo':('synthetic.txt',TEXT.encode())})
    assert response.status_code == 403
    assert '99999999' not in response.text

def test_pseudonym_endpoint_does_not_return_mapping():
    response=client.post('/hcd/pseudonimizar',json={'texto':TEXT})
    assert response.status_code == 200
    assert set(response.json()) == {'texto_pseudonimizado','reemplazos'}
    assert '99999999' not in response.text and 'Persona Sintetica' not in response.text

def test_validation_does_not_echo_input():
    response=client.post('/rag/consulta',json={'pregunta':{'secret':'SYNTHETIC_PRIVATE_MARKER'}})
    assert response.status_code == 422
    assert 'SYNTHETIC_PRIVATE_MARKER' not in response.text

def test_missing_model(synthetic_model,monkeypatch,tmp_path):
    monkeypatch.setattr(main,'MODEL_PATH',tmp_path/'absent.pkl')
    assert client.post('/hcd/procesar-texto',json={'texto':TEXT}).status_code == 503

def test_missing_dictionary(synthetic_model,monkeypatch,tmp_path):
    monkeypatch.setattr(runtime,'PROFESSIONALS_PATH',tmp_path/'absent.json')
    response=client.post('/hcd/procesar-texto',json={'texto':TEXT})
    assert response.status_code == 503
    assert client.get('/hcd/reportes').json() == []

def test_missing_database(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'DB_PATH',tmp_path/'missing'/'test.db')
    assert client.get('/hcd/reportes').status_code == 503

def test_census_invalid_and_mobile_no_exception_leak(monkeypatch):
    def broken(*args):raise ValueError('SYNTHETIC_PRIVATE_MARKER')
    monkeypatch.setattr(main,'_leer_archivo_censo',broken)
    for endpoint in ('/censos/upload','/mobile/upload'):
        response=client.post(endpoint,files={'archivo':('a.csv',b'x,y,z')})
        assert response.status_code == 400
        assert 'SYNTHETIC_PRIVATE_MARKER' not in response.text
    assert client.get('/mobile').status_code == 200

def test_census_persists_only_protected_equality_keys():
    data='Cama;Estado;Area;Paciente;Edad;Documento;codigoHC;Ingreso;Estada\n51 A;Ocupada;Salud Mental;Persona Sintetica;30;99999999;1-99999999-1;01/09/2026;3\n'
    response=client.post('/censos/upload',files={'archivo':('censo.csv',data.encode())})
    assert response.status_code == 200
    files=list(main._MOBILE_UPLOAD_DIR.glob('*.json'))
    assert len(files)==1
    saved=files[0].read_text()
    assert '99999999' not in saved and 'Persona Sintetica' not in saved
    row=json.loads(saved)['data'][0]
    assert row['codigoHC'].startswith('HC-') and row['Documento'].startswith('PAC-')

def test_protection_keeps_deduplication():
    from pipeline.pseudonimizacion.censo_privado import protect_census
    frame=pd.DataFrame({'codigoHC':['1-99999999-1']*2+['1-88888888-1'], 'Documento':['99999999']*2+['88888888'], 'Paciente':['SINTETICO']*3})
    protected=protect_census(frame)
    assert len(protected.drop_duplicates('codigoHC')) == len(frame.drop_duplicates('codigoHC')) == 2
    assert protected.equals(protect_census(protected))
    assert 'Paciente' not in protected

def test_request_size_limit(monkeypatch):
    monkeypatch.setattr(runtime,'MAX_BYTES',10)
    assert client.post('/hcd/procesar-modelo',files={'archivo':('a.txt',b'a'*11)}).status_code==413
    assert client.post('/hcd/procesar-texto',content=b'a'*70000).status_code==413

def test_rag_no_embeddings(monkeypatch):
    monkeypatch.setattr(rag_service,'_collection',None)
    monkeypatch.setattr(rag_service,'EMBEDDINGS','')
    assert client.post('/rag/consulta',json={'pregunta':'protocolo sintético'}).status_code==503

def test_rag_retrieval_separate_from_generation_mock(monkeypatch):
    monkeypatch.setattr(rag_service,'retrieve',lambda q,k:[{'id':'synthetic','texto':'Protocolo sintético','fuente':'fixture'}])
    async def no_llm(*args):raise AssertionError('generation called')
    monkeypatch.setattr(main,'generate',no_llm)
    result=client.post('/rag/consulta',json={'pregunta':'protocolo','k':2})
    assert result.status_code==200 and result.json()['generacion_llm'] is False

@pytest.mark.parametrize('error,status', [(httpx.ConnectError('SYNTHETIC_PRIVATE_MARKER'),503),(httpx.ReadTimeout('SYNTHETIC_PRIVATE_MARKER'),504)])
def test_ollama_transport_errors_mock(monkeypatch,error,status):
    monkeypatch.setenv('OLLAMA_MODEL','synthetic-test-model')
    class FakeClient:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):raise error
    monkeypatch.setattr(llm.httpx,'AsyncClient',FakeClient)
    response=client.post('/llm/resumir',json={'texto':'texto sintético'})
    assert response.status_code==status and 'SYNTHETIC_PRIVATE_MARKER' not in response.text

def test_ollama_rejects_external_host(monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','https://example.com')
    assert client.post('/llm/resumir',json={'texto':'synthetic'}).status_code==503

def test_authentication(monkeypatch):
    monkeypatch.setenv('HCD_API_PASSWORD','synthetic-test-secret')
    assert client.get('/health').status_code==200
    assert client.get('/hcd/reportes').status_code==401
    assert client.get('/hcd/reportes',auth=('operador','synthetic-test-secret')).status_code==200

def test_empty_rag_collection_mock(monkeypatch):
    class Empty:
        def count(self):return 0
    monkeypatch.setattr(rag_service,'collection',lambda:Empty())
    assert client.post('/rag/consulta',json={'pregunta':'sintética'}).status_code==409

def test_ollama_invalid_json_mock(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL','synthetic')
    class Fake:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            return httpx.Response(200,content=b'not json',request=httpx.Request('POST','http://localhost'))
    monkeypatch.setattr(llm.httpx,'AsyncClient',Fake)
    response=client.post('/llm/resumir',json={'texto':'sintético'})
    assert response.status_code==502

@pytest.mark.parametrize('extension',['html','xls','xlsx'])
def test_valid_census_formats(extension):
    frame=pd.DataFrame([{'Cama':'51 A','Estado':'Ocupada','Area':'Salud Mental','Paciente':'Persona Sintetica','Edad':30,'Documento':'99999999','codigoHC':'1-99999999-1','Ingreso':'01/09/2026','Estada':3}])
    if extension=='xlsx':
        buffer=io.BytesIO();frame.to_excel(buffer,index=False);content=buffer.getvalue()
    else:
        content=frame.to_html(index=False).encode()
    response=client.post('/censos/upload',files={'archivo':('synthetic.'+extension,content)})
    assert response.status_code==200
    assert response.json()['filas_salud_mental']==1
    assert '99999999' not in response.text

def test_valid_hcd_html(synthetic_model):
    html='<html><body>'+''.join('<p>'+line+'</p>' for line in TEXT.splitlines())+'</body></html>'
    response=client.post('/hcd/procesar-modelo',files={'archivo':('synthetic.xls',html.encode())})
    assert response.status_code==200
    assert response.json()['total_intervenciones']==1

def test_census_html_preserves_leading_zero_identifiers(tmp_path):
    from pipeline.censo.modulo_censo_mensual import leer_archivo_censo
    frame=pd.DataFrame([{'Cama':'51 A','Estado':'Ocupada','Area':'Salud Mental','Documento':'00001234','codigoHC':'000001','Ingreso':'01/09/2026','Estada':'03'}])
    path=tmp_path/'synthetic.html';path.write_text(frame.to_html(index=False))
    parsed=leer_archivo_censo(path)
    assert parsed.iloc[0]['Documento']=='00001234'
    assert parsed.iloc[0]['codigoHC']=='000001'
