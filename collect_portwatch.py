# -*- coding: utf-8 -*-
"""
IMF PortWatch (https://portwatch.imf.org) 무료 REST API 수집기
- 항만별 일별 입항 척수·수입/수출 톤수 (Daily_Trade_Data)  → 세계지도 버블차트 소스
- 초크포인트(수에즈·파나마·호르무즈·바브엘만데브·말라카·희망봉) 일별 통항 척수 (Daily_Chokepoints_Data)
- 실행: python collect_portwatch.py  (증분: DB 마지막 날짜부터)
※ 레이어 URL(FeatureServer 경로)은 portwatch.imf.org 'Data & API' 메뉴에서 최신 값 확인 후 LAYERS에 반영.
"""
import requests, datetime as dt, time
from common import conn, upsert_obs, ensure_indicator, log, latest_date

LAYERS = {
    # 이름: (FeatureServer query URL, 항목 필드, 값 필드들)
    'ports': ('https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Trade_Data/FeatureServer/0/query',
              'portid', {'portcalls': 'CALLS', 'import': 'IMPORT_T', 'export': 'EXPORT_T'}),
    'chokepoints': ('https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query',
                    'portid', {'n_total': 'TRANSITS', 'n_container': 'TRANSITS_CONT', 'n_dry_bulk': 'TRANSITS_BULK', 'n_tanker': 'TRANSITS_TANK'}),
}
# 대시보드에 올릴 항만/초크포인트 id (PortWatch portid) — 사이트 지도에서 클릭해 id 확인 후 채움
WATCH = {
    'ports': ['port1114', 'port1245', 'port1131', 'port911', 'port1050', 'port1059', 'port1247', 'port1052', 'port929', 'port980', 'port1058', 'port1104', 'port1246', 'port1109'],
    'chokepoints': ['chokepoint1', 'chokepoint2', 'chokepoint3', 'chokepoint4', 'chokepoint5', 'chokepoint6'],
}

def query(url, where, out_fields='*', offset=0):
    r = requests.get(url, params={'where': where, 'outFields': out_fields, 'f': 'json', 'resultOffset': offset,
                                  'resultRecordCount': 2000, 'orderByFields': 'date ASC'}, timeout=60)
    r.raise_for_status()
    return r.json()

def main():
    c = conn()
    for layer, (url, idf, valmap) in LAYERS.items():
        ids = WATCH[layer]
        for pid in ids:
            try:
                code0 = f'PW_{pid.upper()}_{list(valmap.values())[0]}'
                last = latest_date(c, code0)
                since = (dt.date.fromisoformat(last) - dt.timedelta(days=7)) if last else dt.date(2019, 1, 1)
                where = f"{idf}='{pid}' AND date >= DATE '{since:%Y-%m-%d}'"
                rows, offset = [], 0
                while True:
                    js = query(url, where, offset=offset)
                    feats = js.get('features', [])
                    for f in feats:
                        a = f['attributes']
                        d = dt.datetime.utcfromtimestamp(a['date'] / 1000).strftime('%Y-%m-%d') if isinstance(a['date'], (int, float)) else str(a['date'])[:10]
                        name = a.get('portname') or a.get('name') or pid
                        for src, suffix in valmap.items():
                            code = f'PW_{pid.upper()}_{suffix}'
                            ensure_indicator(c, code, f'{name} {suffix}', '물동량(PortWatch)', 'D', 'PORTWATCH', source_ref=url)
                            rows.append((code, d, a.get(src)))
                    if len(feats) < 2000:
                        break
                    offset += 2000
                    time.sleep(0.3)
                n = upsert_obs(c, rows, url)
                log(c, f'portwatch_{pid}', 'OK', n)
            except Exception as e:
                log(c, f'portwatch_{pid}', 'FAIL', 0, repr(e))

if __name__ == '__main__':
    main()
