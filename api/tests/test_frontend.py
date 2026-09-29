"""UI smoke tests use explicit API mocks; real HTTP is checked separately."""
import json
from pathlib import Path
import pytest
import requests
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[2]
MODULES=['📋 Censo Mensual','📊 Internaciones SM','Ingresar HC','OCR','Pseudonimizacion','Procesamiento NLP','RAG','LLM local','Interconsultas HCD','Metricas HCD','Resumen HCs','Auditoría','Informe']

@pytest.mark.parametrize('module',MODULES)
def test_frontend_empty_api_mock(monkeypatch,module):
    def reply(self,method,url,**kwargs):
        response=requests.Response();response.status_code=200
        data=[] if any(s in url for s in ('/hcd/reportes','/rag/documentos','/episodios/','/reingresos/')) else {}
        response._content=json.dumps(data).encode();return response
    monkeypatch.setattr(requests.Session,'request',reply)
    app=AppTest.from_file(str(ROOT/'frontend/app.py'),default_timeout=15).run()
    app.sidebar.radio[0].set_value(module).run()
    assert len(app.exception)==0

@pytest.mark.parametrize('module',['Metricas HCD','Informe','RAG','Resumen HCs','Auditoría'])
def test_frontend_api_down_mock(monkeypatch,module):
    def down(*args,**kwargs):raise requests.ConnectionError('SYNTHETIC_PRIVATE_MARKER')
    monkeypatch.setattr(requests.Session,'request',down)
    app=AppTest.from_file(str(ROOT/'frontend/app.py'),default_timeout=15).run()
    app.sidebar.radio[0].set_value(module).run()
    assert len(app.exception)==0
    assert any('API' in e.value for e in app.error)
    assert all('SYNTHETIC_PRIVATE_MARKER' not in e.value for e in app.error)
