import sqlite3
import pytest
from scripts.private_backup import backup,restore

def test_backup_restore_and_no_overwrite(tmp_path):
    db=tmp_path/'source.db'
    with sqlite3.connect(db) as con:
        con.execute('create table synthetic(value integer)')
        con.execute('insert into synthetic values(42)')
    private=tmp_path/'synthetic.json';private.write_text('{"synthetic":true}')
    bundle=tmp_path/'backup';backup(db,bundle,[private])
    restored=tmp_path/'restored';restore(bundle,restored)
    with sqlite3.connect(restored/'database.sqlite3') as con:
        assert con.execute('select value from synthetic').fetchone()[0]==42
    assert (restored/'asset_000').read_bytes()==private.read_bytes()
    with pytest.raises(ValueError):restore(bundle,restored)
    with pytest.raises(ValueError):backup(db,bundle,[])
