"""Local, non-destructive SQLite backup/restore; NEVER add generated backups to Git."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from urllib.parse import quote


def check_db(path):
    with sqlite3.connect(f'file:{quote(str(path.resolve()))}?mode=ro', uri=True) as con:
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')


def backup(database, destination, private_files):
    os.umask(0o077)
    if destination.exists():
        raise ValueError('Destination must not already exist')
    check_db(database)
    destination.mkdir(parents=True, mode=0o700)
    with sqlite3.connect(f'file:{quote(str(database.resolve()))}?mode=ro', uri=True) as source:
        with sqlite3.connect(destination/'database.sqlite3') as target:
            source.backup(target)
    check_db(destination/'database.sqlite3')
    assets=[]
    for index, path in enumerate(private_files):
        if not path.is_file() or path.is_symlink():
            raise ValueError('Private inputs must be regular files')
        name=f'asset_{index:03d}'
        shutil.copyfile(path,destination/name)
        assets.append({'file':name,'source_name':path.name})
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
    (destination/'manifest.json').write_text(json.dumps({'files':hashes,'private_assets':assets},indent=2))


def restore(source, destination):
    os.umask(0o077)
    if destination.exists():
        raise ValueError('Restore destination must not already exist')
    manifest=json.loads((source/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        path=source/name
        if Path(name).name!=name or path.is_symlink() or not path.is_file():
            raise ValueError('Invalid backup manifest')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Backup checksum mismatch')
    check_db(source/'database.sqlite3')
    destination.mkdir(parents=True,mode=0o700)
    for name in manifest['files']:
        shutil.copyfile(source/name,destination/name)
    shutil.copyfile(source/'manifest.json',destination/'manifest.json')
    check_db(destination/'database.sqlite3')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--database',type=Path,required=True);b.add_argument('--destination',type=Path,required=True);b.add_argument('--private',type=Path,action='append',default=[])
    r=sub.add_parser('restore');r.add_argument('--source',type=Path,required=True);r.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='backup':backup(args.database,args.destination,args.private)
        else:restore(args.source,args.destination)
    except Exception:
        print('Operación fallida; origen preservado. Revise rutas, permisos e integridad localmente.')
        raise SystemExit(1)
    print('Operación completa; integridad SQLite y checksums verificados.')
