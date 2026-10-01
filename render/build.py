# -*- coding: utf-8 -*-
"""
Bloomberg 엑셀 → 국면 판정 → 대시보드 HTML 2종 생성.
run_monitor.py 가 호출한다. 단독 실행도 가능: python render/build.py bbg_20260911.xlsx
"""
import json, sys, datetime as dt, pathlib
from collections import OrderedDict
import pandas as pd

R = pathlib.Path(__file__).resolve().parent
OUT = R.parent / 'output'

# ───────────────────────── 1) Bloomberg 엑셀 읽기 (v3/v4 블록 레이아웃 + v1/v2 매트릭스 호환)
def read_bbg(path):
    meta = pd.read_excel(path, sheet_name='tickers').dropna(subset=['ticker', 'code'])
    xl = pd.ExcelFile(path)
    raw = {}
    for sh in [s for s in xl.sheet_names if s.startswith('data')]:
        df = pd.read_excel(path, sheet_name=sh)
        hdrs = [str(h).strip().lower() for h in df.columns]
        blocks = sum(h == 'date' or h.startswith('date.') for h in hdrs) > 1
        if blocks:
            for j, h in enumerate(df.columns):
                if j == 0 or str(h).strip().lower().startswith('date'): continue
                if not str(df.columns[j - 1]).strip().lower().startswith('date'): continue
                d = pd.to_datetime(df.iloc[:, j - 1], errors='coerce')
                v = pd.to_numeric(df.iloc[:, j], errors='coerce')
                s = pd.Series(v.values, index=d).dropna(); s = s[~s.index.isna()]
                if len(s): raw[str(h).strip()] = s
        else:
            d = pd.to_datetime(df.iloc[:, 0], errors='coerce')
            for t in df.columns[1:]:
                s = pd.Series(pd.to_numeric(df[t], errors='coerce').values, index=d).dropna()
                s = s[~s.index.isna()]
                if len(s): raw[str(t).strip()] = s
    series, freq, missing = {}, {}, []
    for _, m in meta.iterrows():
        t = str(m['ticker']).strip(); code = str(m['code']).strip()
        if t not in raw: missing.append((code, t)); continue
        series[code] = [[i.strftime('%Y-%m-%d'), round(float(v), 4)] for i, v in raw[t].items()]
        freq[code] = str(m.get('freq', 'D')).strip()
    return series, freq, missing

# ───────────────────────── 1-1) 해진공 KDCI/KCCI (collect_kobc.py 결과 CSV)
def read_kobc(folder):
    """collect_kobc.py 가 만든 kobc_kdci.csv / kobc_kcci.csv → KDCI_M/KCCI_M 시계열.
    파일이 없으면 조용히 건너뜀(해진공 자동수집을 안 돌렸어도 나머지는 정상 동작)."""
    out, freq = {}, {}
    for fn, col, code, fr in [('kobc_kdci.csv', 'KDCI', 'KDCI_M', 'D'),
                              ('kobc_kcci.csv', 'KCCI', 'KCCI_M', 'W')]:
        p = pathlib.Path(folder) / fn
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p, parse_dates=['Date'], encoding='utf-8-sig')
            if col not in df.columns:
                continue
            rows = [[d.strftime('%Y-%m-%d'), round(float(v), 2)]
                    for d, v in zip(df['Date'], df[col]) if pd.notna(v)]
            if rows:
                out[code] = rows
                freq[code] = fr
        except Exception as e:
            print(f'  [경고] {fn} 읽기 실패: {e!r}')
    return out, freq

# ───────────────────────── 2) 파생지표
def derive(ser):
    if 'CAPE_HOPE' in ser and 'SUEZ' in ser:
        a, b = dict(ser['CAPE_HOPE']), dict(ser['SUEZ'])
        ser['DIVERT_RATIO'] = [[k, round(a[k] / (a[k] + b[k]) * 100, 1)] for k in sorted(set(a) & set(b)) if (a[k] + b[k]) > 0]
    if 'SCFI_BBG' in ser and 'BDI_BBG' in ser:
        b = dict(ser['BDI_BBG']); rows = []
        keys = sorted(b)
        for k, v in ser['SCFI_BBG']:
            kk = k if k in b else (max([x for x in keys if x <= k], default=None))
            if kk: rows.append([k, round(v / b[kk] * 100, 2)])
        ser['CNTR_BULK_RATIO'] = rows
    return ser

# ───────────────────────── 3) 국면 축
AXES = {
 '가격': [('SCFI_BBG', 0, 52), ('WCI', 0, 52), ('BDI_BBG', 0, 52), ('TD3C', 0, 52)],
 '수요': [('IRONORE', 0, 52), ('COPPER_BBG', 0, 52), ('CN_PMI', 0, 52), ('US_ISM', 0, 52), ('KR_EXPORT', 0, 52),
          ('SAIL_CN_US', 0, 52), ('SAIL_KR_US', 0, 52), ('SAIL_CN_KR', 0, 52)],   # 세일링 TEU 적재되면 자동 편입
 '공급제약': [('SUEZ', 1, 156), ('HORMUZ', 1, 156), ('PANAMA', 1, 156), ('CAPE_HOPE', 0, 156), ('SUEZ_DWELL_SN', 0, 156)],
 '비용': [('BRENT_BBG', 0, 52), ('NATGAS', 0, 52)],
 '기후': [('ONI', 0, 156)],
}
READ = {'SCFI_BBG': '상하이발 컨테이너 스팟', 'WCI': '8개 항로 40ft 종합', 'BDI_BBG': '벌크 종합', 'TD3C': 'VLCC 중동→중국 (호르무즈 직격)',
 'IRONORE': '중국 철강 수요', 'COPPER_BBG': '글로벌 제조업', 'CN_PMI': '중국 제조업 경기', 'US_ISM': '미국 제조업 경기', 'KR_EXPORT': '한국 수출 (선행)',
 'SAIL_CN_US': '중국→미국 TEU (관세 front-loading)', 'SAIL_KR_US': '한국→미국 TEU', 'SAIL_CN_KR': '중국→한국 TEU (근해)',
 'SUEZ': '낮을수록 막힘 → 부호 반전', 'HORMUZ': '낮을수록 막힘 → 부호 반전', 'PANAMA': '낮을수록 막힘 → 부호 반전',
 'CAPE_HOPE': '높을수록 우회 진행', 'SUEZ_DWELL_SN': '높을수록 대기 길어짐', 'BRENT_BBG': '선사 연료 원가', 'NATGAS': 'LNG·발전 수요', 'ONI': '+0.5↑ 엘니뇨'}

def weekly(rows):
    o = OrderedDict()
    for d, v in rows:
        if v is None: continue
        x = dt.date.fromisoformat(d); o[(x - dt.timedelta(days=x.weekday()) + dt.timedelta(days=4)).isoformat()] = v
    return o

def zser(w, inv, win):
    ks = sorted(w); out = {}
    for i, k in enumerate(ks):
        s = [w[x] for x in ks[max(0, i - win + 1):i + 1]]
        if len(s) < 12: continue
        m = sum(s) / len(s); sd = (sum((x - m) ** 2 for x in s) / (len(s) - 1)) ** .5
        if sd: out[k] = round((-1 if inv else 1) * (w[k] - m) / sd, 3)
    return out

def regime(ser):
    W = {k: weekly(v) for k, v in ser.items()}
    Z = {a: {c: zser(W[c], bool(i), win) for c, i, win in cs if c in W and len(W[c]) >= 20} for a, cs in AXES.items()}
    allk = sorted({k for a in Z.values() for s in a.values() for k in s})
    axis_ts = {a: [] for a in AXES}
    for k in allk:
        for a, cs in Z.items():
            vals = [s[k] for s in cs.values() if k in s]
            if vals: axis_ts[a].append([k, round(sum(vals) / len(vals), 3)])
    def at(k):
        g = {a: dict(v).get(k) for a, v in axis_ts.items()}
        p, dm, sc = g.get('가격'), g.get('수요'), g.get('공급제약')
        if p is None: return None
        lbl = '상승' if p >= .5 else '하락' if p <= -.5 else '횡보'
        cause, note = None, ''
        if dm is not None and sc is not None:
            if max(abs(dm), abs(sc)) < .4:
                cause, note = '원인 불명확', '수요·공급제약 축 모두 중립 — 계약갱신·선복재배치 등 축 밖 요인. 개별 지표 확인 필요'
            else:
                cause = '수요' if abs(dm) > abs(sc) else '공급제약'
                if abs(abs(dm) - abs(sc)) < .3: cause = '수요·공급 혼합'
        full = f'{cause} 주도 {lbl}' if lbl != '횡보' and cause and cause != '원인 불명확' else (f'{lbl} · {cause}' if cause else lbl)
        return {'axes': g, 'price': lbl, 'cause': cause, 'note': note, 'label': full}
    reg = [[k, at(k)] for k in allk if at(k)]
    parts = []
    for a, cs in AXES.items():
        for c, inv, win in cs:
            if c not in W or len(W[c]) < 20: continue
            z = zser(W[c], bool(inv), win)
            parts.append({'axis': a, 'code': c, 'name': c, 'z': z[sorted(z)[-1]] if z else None, 'read': READ.get(c, '')})
    return W, axis_ts, reg, parts

# ───────────────────────── 4) 이벤트 윈도우
EVC = ['SCFI_BBG', 'WCI', 'BDI_BBG', 'TD3C', 'BRENT_BBG', 'HORMUZ', 'SUEZ', 'KOSPI_BBG', 'SPX', 'US10Y', 'HMM', 'FRO']
def events(W, ev):
    def vat(w, d, n):
        t = (dt.date.fromisoformat(d) + dt.timedelta(weeks=n)).isoformat()
        ks = [k for k in sorted(w) if k <= t]
        return w[ks[-1]] if ks else None
    pct = lambda a, b: None if (a in (None, 0) or b is None) else round((b / a - 1) * 100, 1)
    out = []
    for e in ev:
        row = {'id': e['id']}
        for c in EVC:
            w = W.get(c)
            if not w: continue
            base = vat(w, e['date'], -1)
            if base is None: continue
            st = {'base': base}
            for lbl, n in [('w4', 4), ('w8', 8), ('w12', 12), ('w26', 26)]: st[lbl] = pct(base, vat(w, e['date'], n))
            d0 = dt.date.fromisoformat(e['date'])
            win = [(k, v) for k, v in w.items() if d0 <= dt.date.fromisoformat(k) <= d0 + dt.timedelta(weeks=26)]
            if win:
                mx = max(win, key=lambda x: x[1]); mn = min(win, key=lambda x: x[1])
                st['max'] = pct(base, mx[1]); st['min'] = pct(base, mn[1])
                st['peak_w'] = (dt.date.fromisoformat(mx[0]) - d0).days // 7
            row[c] = st
        out.append(row)
    return out

# ───────────────────────── 5) 렌더
def thin(rows):
    if not rows: return rows
    cut = (dt.date.fromisoformat(rows[-1][0]) - dt.timedelta(days=400)).isoformat()
    o, recent = {}, []
    for d, v in rows:
        if v is None: continue
        if d >= cut: recent.append([d, v]); continue
        x = dt.date.fromisoformat(d); o[(x - dt.timedelta(days=x.weekday()) + dt.timedelta(days=4)).isoformat()] = v
    return [[k, o[k]] for k in sorted(o)] + recent

def kobc_kpi_live(ser, static):
    """KDCI_M/KCCI_M 이 실제로 적재됐으면 해당 카드만 최신값으로 교체, 없는 건 수기 값 유지."""
    labels = {'KDCI_M': 'KDCI 종합 (해진공)', 'KCCI_M': 'KCCI 종합 (해진공)'}
    live = {}
    for code, label in labels.items():
        rows = sorted(ser.get(code) or [])
        if not rows:
            continue
        last_d, last_v = rows[-1]
        prev_v = rows[-2][1] if len(rows) > 1 else None
        chg = f' · {"+" if last_v >= prev_v else ""}{(last_v / prev_v - 1) * 100:.2f}%' if prev_v else ''
        live[label] = {'l': label, 'v': f'{last_v:,.0f}', 'd': f'{last_d}{chg} · 자동(collect_kobc.py)'}
    return [live.get(row['l'], row) for row in static] + [v for k, v in live.items() if k not in {r['l'] for r in static}]

def main(xlsx, offline=True):
    OUT.mkdir(exist_ok=True)
    base = json.load(open(R / 'base_data.json', encoding='utf-8'))
    conf = json.load(open(R / 'dash_conf.json', encoding='utf-8'))
    ser = dict(base['series']); freq = dict(conf['freq_base'])
    miss = []
    if xlsx:
        s2, f2, miss = read_bbg(xlsx)
        ser.update(s2); freq.update(f2)
        print(f'  Bloomberg {len(s2)}계열 적재' + (f' / 미조회 {len(miss)}개: ' + ', '.join(c for c, _ in miss[:6]) + ('…' if len(miss) > 6 else '') if miss else ''))
        if len(s2) == 0:
            print('  [경고] 적재된 계열이 0개입니다 — Refresh All 후 값이 아닌 빈 템플릿을 지정했을 수 있습니다.')
    kobc_dirs = [R.parent / 'inbox'] + ([pathlib.Path(xlsx).parent] if xlsx else [])
    for d in dict.fromkeys(kobc_dirs):
        if not d.is_dir():
            continue
        ks, kf = read_kobc(d)
        if ks:
            ser.update(ks); freq.update(kf)
            print(f'  해진공 {len(ks)}계열 적재 (' + ', '.join(ks) + f') ← {d}')
    ser = derive(ser)
    W, axis_ts, reg, parts = regime(ser)
    ev = base['events']
    stats = events(W, ev)
    data = {'series': {c: thin(r) for c, r in ser.items()}, 'events': ev, 'event_stats': stats, 'freq': freq}
    kobc_kpi = kobc_kpi_live(ser, conf['kobc_kpi'])
    tpl = open(R / 'dash_template3.html', encoding='utf-8').read()
    J = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))
    land = json.load(open(R / 'land-110m.json', encoding='utf-8'))
    built_at = dt.datetime.now().strftime('%Y-%m-%d %H:%M')   # 빌드 실행 시각(서버/PC 시계 기준 — 브라우저 시계 아님)
    made = []
    for mode, title, badge, fn in [('internal', '해운·물류 지표 모니터 (내부)', f'INTERNAL · 내부 검토용 · 갱신 {built_at}', 'dashboard_내부검토용.html'),
                                   ('public', '해운·물류 지표 모니터', f'PUBLIC · 공표용 · 갱신 {built_at}', 'dashboard_외부공표용.html')]:
        h = tpl
        h = h.replace("const kp = KPI_SPEC", "const kp = " + J(kobc_kpi) + ".concat(KPI_SPEC")
        i = h.index("const kp = "); j = h.index("});", i); h = h[:j] + "}));" + h[j + 3:]
        for k, v in [('__MODE__', mode), ('__TITLE__', title), ('__BADGE__', badge), ('__DATA__', J(data)), ('__LAND__', J(land)),
                     ('__PORTS__', J(conf['ports'])), ('__CHOKES__', J(conf['chokes'])), ('__INFO__', J(conf['info'])),
                     ('__REL__', J(conf['rel'])), ('__PATTERN__', J(conf['pattern'])), ('__SRC__', J(conf['src'])),
                     ('__LINKS__', J(conf['links'])), ('__AXIS__', J({a: v[-170:] for a, v in axis_ts.items()})),
                     ('__REGIME__', J(reg[-170:])), ('__PARTS__', J(parts)), ('__MATRIX__', J(conf['matrix'])), ('__AXISDOC__', J(conf['axisdoc']))]:
            h = h.replace(k, v)
        if offline:
            h = h.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>', '<script>' + open(R / 'd3.min.js', encoding='utf-8').read() + '</script>')
            h = h.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>', '<script>' + open(R / 'topojson-client.min.js', encoding='utf-8').read() + '</script>')
        p = OUT / fn
        tmp = p.with_suffix('.tmp'); tmp.write_text(h, encoding='utf-8'); tmp.replace(p)   # 원자적 교체
        made.append(p)
    r = reg[-1]
    print(f'  국면 판정: {r[1]["label"]}  ({r[0]} 기준)')
    print('  축: ' + ' · '.join(f'{a} {v:+.2f}' for a, v in r[1]['axes'].items() if v is not None))
    return made

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
