"""Conservative publication checks; reports filenames only, never matched values."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def check():
    files=subprocess.check_output(['git','ls-files','--cached'],text=True).splitlines()
    errors=[]
    private=Path('.local/profesionales.json')
    names=[]
    if private.exists():
        names=[name for values in json.loads(private.read_text()).values() for name in values]
    for name in files:
        p=Path(name)
        if name.startswith(('.local/','.venv','uploads/','outputs/','rag/db/','rag/db-reviewed/')) or p.suffix in {'.db','.sqlite','.sqlite3','.pkl','.xls','.xlsx'} or p.name=='.env':
            errors.append((name,'private path/type'));continue
        if not p.is_file():continue
        if p.suffix in {'.py','.md','.json','.txt','.yml','.yaml','.toml','.lock','.example','.html'}:
            text=p.read_text(errors='replace')
        elif p.suffix=='.pdf' and not name.startswith('rag/protocolos/'):
            from pypdf import PdfReader
            text='\n'.join(page.extract_text() or '' for page in PdfReader(p).pages)
        else:continue
        # The author explicitly requested her full name in the academic deliverable.
        text=text.replace('Silvia Andrea Gómez Villagra', '[AUTORA]')
        if any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',text,re.IGNORECASE) for n in names if len(n)>4):
            errors.append((name,'private dictionary match'))
        if re.search(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',text):
            errors.append((name,'credential pattern'))
    return {'tracked_files_checked':len(files),'dictionary_check_available':private.exists(),'errors':[{'path':p,'reason':r} for p,r in errors], 'limitation':'Heuristic scan plus source review; cannot prove absence of all PII, especially in historical commits.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=check()
    if args.output:args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(bool(result['errors']))
