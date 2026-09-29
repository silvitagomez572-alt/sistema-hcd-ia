"""Install committed source into a clean venv and test; excludes all private files."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    work=Path(tempfile.mkdtemp(prefix='hcd-clean-release-'))
    source=work/'source';source.mkdir()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    archive=work/'source.tar'
    with archive.open('wb') as output:subprocess.run(['git','archive','HEAD'],cwd=ROOT,stdout=output,check=True)
    with tarfile.open(archive) as bundle:bundle.extractall(source,filter='data')
    venv.EnvBuilder(with_pip=True).create(work/'venv')
    python=work/'venv/bin/python'
    result={'source_commit':revision,'private_files_copied':False,'checks':{}}
    commands=[('install',[str(python),'-m','pip','install','-r','requirements.txt']),('pip_check',[str(python),'-m','pip','check']),('pytest',[str(python),'-m','pytest','api/tests','-v','--tb=short'])]
    for name,command in commands:
        with (work/(name+'.log')).open('w') as log:completed=subprocess.run(command,cwd=source,stdout=log,stderr=subprocess.STDOUT)
        result['checks'][name]=completed.returncode
        if completed.returncode:
            result['blocked_at']=name;break
    (ROOT/'entrega/validacion_instalacion_limpia.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));print('Logs sintéticos de instalación:',work)
    raise SystemExit(any(result['checks'].values()))
