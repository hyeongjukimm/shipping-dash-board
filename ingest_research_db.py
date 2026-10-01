# -*- coding: utf-8 -*-
"""
리서치센터 DB(research-mcp / DB-Ready 데이터) 적재기
- 이미 센터 DB에 있는 시계열(SCFI, CCFI, BDI, 원자재, 금리, 주가지수 등)은 재수집하지 않고 API에서 가져온다.
- 접속 방식은 센터 내부 규격에 맞게 fetch_timeseries() 한 함수만 교체하면 된다.
  (예: MCP get_timeseries(dataset_code, columns, start) 호출 결과 JSON {rows:[{date,col:val}]})
"""
import json, datetime as dt
from common import conn, upsert_obs, ensure_indicator, log, latest_date

# (dataset_code, {컬럼: 지표코드}, freq, group)
MAP = [
    ('shipping_SCFI_컨테이너_운임', {'scfi_overall': 'SCFI', 'scfi_wc_america': 'SCFI_USWC', 'scfi_ec_america': 'SCFI_USEC', 'scfi_europe': 'SCFI_EUR', 'scfi_mediterranean': 'SCFI_MED', 'scfi_se_asia': 'SCFI_SEA'}, 'W', '컨테이너(외부)'),
    ('shipping_CCFI_컨테이너_운임', {'ccfi_overall': 'CCFI', 'ccfi_korea': 'CCFI_KR', 'ccfi_europe': 'CCFI_EUR', 'ccfi_wc_america': 'CCFI_USWC', 'ccfi_persian_red_sea': 'CCFI_REDSEA'}, 'W', '컨테이너(외부)'),
    ('shipping_BDI_벌크_운임', {'bdi': 'BDI', 'bci': 'BCI', 'avg_bci_5tc': 'BCI_5TC', 'avg_bpi_82_5tc': 'BPI_5TC'}, 'D', '벌크(외부)'),
    ('shipping_벌크_화물', {'iron_ore': 'TRADE_IRONORE', 'coal': 'TRADE_COAL', 'dry_bulk': 'TRADE_DRYBULK'}, 'M', '물동량'),
    ('clarksons_newbuilding_index', None, 'W', '선가'),
    ('clarksons_secondhand_index', None, 'M', '선가'),
    ('RM_major', {'RM_brentoil_value': 'BRENT', 'RM_wti_value': 'WTI', 'RM_copper_value': 'COPPER', 'RM_corn_value': 'CORN', 'RM_naturalgas_value': 'NATGAS'}, 'D', '원자재'),
    ('TS_by_country', {'TS_us_value': 'US_TS_10Y2Y'}, 'D', '금리'),
    ('BR_by_country', None, 'D', '금리'),
    ('world_exchange_index', {'코스피': 'KOSPI', 'S&P500': 'SPX', '상해 종합': 'SHCOMP', '독일': 'DAX'}, 'D', '주가지수'),
    ('spx_sector_index', None, 'D', '섹터'),
    ('aviation_환율_및_유가', None, 'D', '환율'),
]

def fetch_timeseries(dataset_code, columns, start):
    """센터 내부 API 호출부. MCP 환경이면 get_timeseries 결과 JSON을 그대로 반환하도록 구현."""
    raise NotImplementedError('센터 DB 접속 규격에 맞게 구현: return {"rows":[{"date":..., col: val}]}')

def main():
    c = conn()
    for ds, colmap, freq, group in MAP:
        if colmap is None:
            continue   # 스키마 확인 후 컬럼 매핑 채우면 활성화
        try:
            first = list(colmap.values())[0]
            last = latest_date(c, first)
            start = (dt.date.fromisoformat(last) - dt.timedelta(days=30)).isoformat() if last else '2015-01-01'
            js = fetch_timeseries(ds, list(colmap.keys()), start)
            rows = []
            for col, code in colmap.items():
                ensure_indicator(c, code, col, group, freq, 'RESEARCH_DB', source_ref=ds)
                rows += [(code, r['date'], r.get(col)) for r in js['rows'] if r.get(col) is not None]
            log(c, f'researchdb_{ds}', 'OK', upsert_obs(c, rows, ds))
        except Exception as e:
            log(c, f'researchdb_{ds}', 'FAIL', 0, repr(e))

if __name__ == '__main__':
    main()
