# -*- coding: utf-8 -*-
"""공통 유틸: DB 연결, 적재, 로그"""
import sqlite3, datetime as dt, os, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'shipping.db'
INBOX = ROOT / 'inbox'      # Bloomberg 엑셀 등 사람이 드롭하는 폴더
ARCHIVE = ROOT / 'archive'  # 적재 완료 원본 보관

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(open(ROOT / 'schema.sql', encoding='utf-8').read())
    return c

def upsert_obs(c, rows, source_file=None):
    """rows: iterable of (code, 'YYYY-MM-DD', value). 같은 (code,date)면 덮어씀(정정치 반영)."""
    now = dt.datetime.now().isoformat(timespec='seconds')
    data = [(code, d, None if v in ('', None) else float(v), now, source_file) for code, d, v in rows if d]
    c.executemany('INSERT OR REPLACE INTO observation(code,obs_date,value,loaded_at,source_file) VALUES(?,?,?,?,?)', data)
    c.commit()
    return len(data)

def ensure_indicator(c, code, name_ko, group_name, freq, source, unit=None, source_ref=None, bbg_ticker=None, release_rule=None):
    c.execute('''INSERT INTO indicator(code,name_ko,group_name,unit,freq,source,source_ref,bbg_ticker,release_rule)
                 VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO NOTHING''',
              (code, name_ko, group_name, unit, freq, source, source_ref, bbg_ticker, release_rule))
    c.commit()

def log(c, job, status, rows=0, message=''):
    c.execute('INSERT INTO load_log(run_at,job,status,rows_loaded,message) VALUES(?,?,?,?,?)',
              (dt.datetime.now().isoformat(timespec='seconds'), job, status, rows, message[:2000]))
    c.commit()
    print(f'[{job}] {status} rows={rows} {message}')

def latest_date(c, code):
    r = c.execute('SELECT MAX(obs_date) FROM observation WHERE code=?', (code,)).fetchone()
    return r[0]
