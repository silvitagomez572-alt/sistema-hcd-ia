"""All tests use isolated synthetic state, including import/startup."""
import os
import tempfile
from pathlib import Path
import json
import pytest

_SESSION = tempfile.TemporaryDirectory(prefix='hcd-tests-')
os.environ['HCD_DB_PATH'] = str(Path(_SESSION.name) / 'startup.db')
os.environ['HCD_UPLOAD_DIR'] = str(Path(_SESSION.name) / 'uploads')
os.environ['HCD_API_PASSWORD'] = ''
os.environ['HCD_PROFESSIONALS_PATH'] = str(Path(_SESSION.name) / 'profesionales.json')
Path(os.environ['HCD_PROFESSIONALS_PATH']).write_text(json.dumps({'enfermeria': ['profesional sintetico alfa']}))

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    from api import main, runtime
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'test.db')
    monkeypatch.setattr(main, '_MOBILE_UPLOAD_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(main, 'HCD_PATH', tmp_path / 'missing.json')
    monkeypatch.setattr(main, '_modelo_nlp', None)
    monkeypatch.setattr(main, 'PROFESIONALES_SALUD_MENTAL', None)
    monkeypatch.setattr(runtime, 'PROFESSIONALS_PATH', Path(os.environ['HCD_PROFESSIONALS_PATH']))
    monkeypatch.delenv('HCD_ALLOW_DELETE', raising=False)
    main.init_db()

@pytest.fixture
def synthetic_model(tmp_path, monkeypatch):
    import joblib
    from sklearn.pipeline import make_pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from api import main
    model = make_pipeline(TfidfVectorizer(), LogisticRegression(random_state=0))
    model.fit(['cuidados signos vitales', 'medicacion asistencia', 'entrevista emocional', 'abordaje vincular'], ['Enfermería','Enfermería','Psicología','Psicología'])
    path = tmp_path / 'synthetic.pkl'
    joblib.dump(model, path)
    monkeypatch.setattr(main, 'MODEL_PATH', path)
    return path
