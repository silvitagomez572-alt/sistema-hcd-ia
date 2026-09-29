#!/usr/bin/env bash
set -euo pipefail
# Only synthetic files and a dedicated project/volumes; no institutional mounts.
validation_private=$(mktemp -d /tmp/hcd-docker-private-XXXXXX)
chmod 755 "$validation_private"
export HCD_PRIVATE_DIR="$validation_private"
export HCD_API_PASSWORD=synthetic-validation
export HCD_API_PORT=18010
export HCD_FRONTEND_PORT=18510
validation_project="hcd-validation-$(date +%s)"
python_bin=${HCD_VALIDATION_PYTHON:-.venv-hardening/bin/python}
"$python_bin" - "$validation_private" <<'PY'
import json,sys,joblib
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
root=Path(sys.argv[1]);(root/'profesionales.json').write_text(json.dumps({'enfermeria':['profesional sintetico alfa']}))
model=make_pipeline(TfidfVectorizer(),LogisticRegression(solver='liblinear',random_state=0))
model.fit(['enfermeria cuidados','psicologia entrevista'],['Enfermería','Psicología']);joblib.dump(model,root/'modelo_area_intervenciones.pkl')
for p in root.iterdir():p.chmod(0o644)
PY
trap 'docker compose -p "$validation_project" down >/dev/null 2>&1 || true' EXIT
docker compose -p "$validation_project" up -d --no-build
"$python_bin" - <<'PY'
import time,json,requests
from pathlib import Path
base='http://127.0.0.1:18010';auth=('operador','synthetic-validation')
for _ in range(90):
 try:
  if requests.get(base+'/health',timeout=2).status_code==200 and requests.get('http://127.0.0.1:18510/_stcore/health',timeout=2).status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
else:raise RuntimeError('Docker health timeout')
text='01/09/2026 - 10:00 hs\nNota de enfermería\nControl de signos vitales y cuidados generales del turno.'
r=requests.post(base+'/hcd/procesar-modelo',files={'archivo':('synthetic.txt',text.encode())},auth=auth,timeout=30)
assert r.status_code==200 and r.json()['total_intervenciones']==1
results={'compose_up':True,'api_health':200,'frontend_health':200,'synthetic_processing':200,'private_fixture':'synthetic only','volumes':'dedicated validation project; institutional data untouched'}
Path('entrega/validacion_docker.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps(results))
PY
