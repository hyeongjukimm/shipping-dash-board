# -*- coding: utf-8 -*-
"""
Bloomberg 수동 추출 파일 적재기
- 크롤링 불가 지표(WCI, FBX, HARPEX, BDTI/BCTI, ClarkSea, 벙커유, BEI 등)는 담당자가 터미널에서
  bbg_template.xlsx(시트 'data': A열 Date, 1행 티커)를 BDH로 갱신 → inbox/ 폴더에 저장.
- 본 스크립트가 inbox/*.xlsx 를 감지해 long format으로 적재하고 archive/로 이동.
- 티커→지표코드 매핑은 시트 'tickers'(ticker, code, name_ko, group, unit, freq)에서 읽는다.
- 실행: python ingest_bloomberg.py   (스케줄러에서 매일 1회 또는 폴더 감시)
"""
import pandas as pd, shutil, datetime as dt
from common import conn, upsert_obs, ensure_indicator, log, INBOX, ARCHIVE

def _read_blocks(df):
    """v3 블록 레이아웃: 1행 'Date'|티커 반복. → {티커: Series(index=date)}"""
    out = {}
    cols = list(df.columns)
    for j, h in enumerate(cols):
        if str(h).strip().lower().startswith('date') or j == 0:
            continue
        if j >= 1 and str(cols[j - 1]).strip().lower().startswith('date'):
            d = pd.to_datetime(df.iloc[:, j - 1], errors='coerce')
            v = pd.to_numeric(df.iloc[:, j], errors='coerce')
            s = pd.Series(v.values, index=d).dropna()
            s = s[~s.index.isna()]
            out[str(h).strip()] = s
    return out

def _read_matrix(df):
    """v1/v2 레이아웃: A열 Date, 1행 티커."""
    df = df.rename(columns={df.columns[0]: 'Date'})
    d = pd.to_datetime(df['Date'], errors='coerce')
    return {str(t).strip(): pd.Series(pd.to_numeric(df[t], errors='coerce').values, index=d).dropna() for t in df.columns[1:]}

def ingest(path, c):
    meta = pd.read_excel(path, sheet_name='tickers').dropna(subset=['ticker', 'code'])
    xl = pd.ExcelFile(path)
    series = {}
    for sh in [s for s in xl.sheet_names if s.startswith('data')]:
        df = pd.read_excel(path, sheet_name=sh)
        hdrs = [str(h).strip().lower() for h in df.columns]
        series.update(_read_blocks(df) if hdrs.count('date') + sum(h.startswith('date.') for h in hdrs) > 1 else _read_matrix(df))
    rows = []
    for _, m in meta.iterrows():
        t = str(m['ticker']).strip()
        if t not in series or series[t].empty:
            continue
        group = f"{m.get('axis(축)', '')}|{m.get('group', 'Bloomberg')}"
        ensure_indicator(c, m['code'], m.get('name_ko', t), group, str(m.get('freq', 'D')), 'BLOOMBERG', unit=m.get('unit'), bbg_ticker=t)
        rows += [(m['code'], d.strftime('%Y-%m-%d'), float(v)) for d, v in series[t].items()]
    return upsert_obs(c, rows, path.name)

def main():
    c = conn()
    for f in sorted(INBOX.glob('*.xls*')):
        try:
            n = ingest(f, c)
            shutil.move(str(f), ARCHIVE / f'{dt.datetime.now():%Y%m%d_%H%M%S}_{f.name}')
            log(c, 'bloomberg_ingest', 'OK', n, f.name)
        except Exception as e:
            log(c, 'bloomberg_ingest', 'FAIL', 0, f'{f.name}: {e!r}')

if __name__ == '__main__':
    main()
