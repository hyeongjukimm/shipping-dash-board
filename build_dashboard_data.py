# -*- coding: utf-8 -*-
"""
DB → 대시보드 데이터(dash_data.json) 생성 + 이벤트 윈도우 재계산
- 대시보드 HTML은 이 JSON 하나만 읽는다(정적 파일 → 사내 공유폴더/인트라넷에 그대로 배포 가능).
- 실행: python build_dashboard_data.py  (모든 수집 잡 뒤에 실행)
"""
import json, datetime as dt, sqlite3
from collections import defaultdict
from common import conn, log, ROOT

WINDOWS = {'w4': 4, 'w8': 8, 'w12': 12, 'w26': 26}
# 이벤트 비교에 쓸 대표 지표 (존재하는 것만 계산)
EVENT_CODES = ['KCCI', 'KDCI', 'SCFI', 'CCFI', 'BDI', 'BRENT', 'US10Y', 'US_TS_10Y2Y', 'KOSPI', 'SPX', 'HMM', 'MAERSK']

def weekly_last(rows):
    """일별/주별 혼합 시계열을 '해당 주 금요일' 키로 정규화(마지막 관측값)."""
    out = {}
    for d, v in rows:
        if v is None: continue
        dd = dt.date.fromisoformat(d)
        fri = dd - dt.timedelta(days=dd.weekday()) + dt.timedelta(days=4)
        out[fri.isoformat()] = v
    return out

def value_at(sr, date, weeks):
    target = dt.date.fromisoformat(date) + dt.timedelta(weeks=weeks)
    best = None
    for k in sr:           # sr는 날짜순 dict
        if dt.date.fromisoformat(k) <= target: best = k
        else: break
    return sr.get(best) if best else None

def pct(a, b): return None if (a in (None, 0) or b is None) else round((b / a - 1) * 100, 1)

def main():
    c = conn()
    c.row_factory = sqlite3.Row
    inds = {r['code']: dict(r) for r in c.execute('SELECT * FROM indicator WHERE active=1')}
    series = defaultdict(list)
    for r in c.execute('SELECT code, obs_date, value FROM observation ORDER BY code, obs_date'):
        series[r['code']].append([r['obs_date'], r['value']])
    events = [dict(r) for r in c.execute('SELECT * FROM event ORDER BY event_date')]

    # 이벤트 윈도우
    c.execute('DELETE FROM event_window')
    stats = []
    for e in events:
        row = {'event_id': e['event_id']}
        for code in EVENT_CODES:
            if code not in series: continue
            sr = dict(sorted(weekly_last(series[code]).items()))
            base = value_at(sr, e['event_date'], -1)
            st = {'base': base}
            for k, w in WINDOWS.items():
                st[k] = pct(base, value_at(sr, e['event_date'], w))
            d0 = dt.date.fromisoformat(e['event_date'])
            win = [(k, v) for k, v in sr.items() if d0 <= dt.date.fromisoformat(k) <= d0 + dt.timedelta(weeks=26)]
            if win and base:
                mx = max(win, key=lambda x: x[1]); mn = min(win, key=lambda x: x[1])
                st['max'] = pct(base, mx[1]); st['min'] = pct(base, mn[1])
                st['weeks_to_peak'] = (dt.date.fromisoformat(mx[0]) - d0).days // 7
            row[code] = st
            c.execute('INSERT INTO event_window VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (e['event_id'], code, base, st.get('w4'), st.get('w8'), st.get('w12'), st.get('w26'), st.get('max'), st.get('min'), st.get('weeks_to_peak')))
        stats.append(row)
    c.commit()

    # 최신값·변화율 요약 (KPI 타일용)
    latest = {}
    for code, rows in series.items():
        rows = [r for r in rows if r[1] is not None]
        if not rows: continue
        last = rows[-1]
        def back(n):
            return rows[-1 - n][1] if len(rows) > n else None
        freq = inds.get(code, {}).get('freq', 'D')
        step_w = 1 if freq == 'W' else 5   # 일별이면 5영업일 ≈ 1주
        latest[code] = {'date': last[0], 'value': last[1],
                        'wow': pct(back(step_w), last[1]), 'mom': pct(back(step_w * 4), last[1]),
                        'ytd': None}
    ports = [dict(r) for r in c.execute('SELECT * FROM port')]
    commentary = [dict(r) for r in c.execute('SELECT * FROM commentary ORDER BY pub_date DESC LIMIT 50')]
    related = [dict(r) for r in c.execute('SELECT * FROM related_asset')]

    out = {'built_at': dt.datetime.now().isoformat(timespec='minutes'),
           'indicators': inds, 'series': series, 'latest': latest,
           'events': events, 'event_stats': stats, 'ports': ports, 'commentary': commentary, 'related': related}
    (ROOT / 'data' / 'dash_data.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    log(c, 'build_dashboard_data', 'OK', len(series), 'dash_data.json')

if __name__ == '__main__':
    main()
