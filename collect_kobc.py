# -*- coding: utf-8 -*-
"""
해진공(KOBC) 해양정보서비스 - 순수 HTTP 요청 버전 (브라우저 / Playwright 불필요)

[발견한 사실 - 개발자도구 Network 탭으로 확인함]
이 사이트는 표를 자바스크립트로 그리는 게 아니라, 날짜 검색 폼을 그대로 서버에
POST 하면 서버가 완성된 HTML 표를 통째로 내려주는 구식(JSP) 방식이다.
즉 Playwright로 화면을 띄우고 클릭할 필요 없이, requests 로 폼을 그대로
제출하기만 하면 몇 년치 일별 데이터를 한 번에 받을 수 있다.

  POST https://www.kobc.or.kr/ebz/shippinginfo/kdci/gridList.do?mId=0301000000
  body: sources=kdci&page=1&sDay=2022-01-01&eDay=2026-09-11&siteCode=shippinginfo&mId=0301000000

지원 (날짜 범위 조회 가능, 자동화 검증됨):
  - kdci : 건화물선운임지수 (KDCI/CAPE/PANAMAX/SUPRAMAX/HANDY 한 표에 다 나옴)
  - kcci : 컨테이너선운임지수 (KCCI 등 13개 항로, sources=kcci 로 동일 구조)

미지원 (자동화 불안정 - 계속 수기 확인 권장):
  - ncfi : 닝보 컨테이너선운임지수 - 날짜 범위가 아니라 "단일 날짜" 검색이고
           기본 화면은 "No data" 상태. 매주 특정 발표일에만 값이 채워짐.
  - kpli : KOBC 항만∙물류지표 - 사이트 공지상 "시험발간중"이라 데이터 자체가 없음.

※ 주의: 이 스크립트는 사용자 PC(또는 회사 네트워크)에서 실행해야 한다.
   클라우드 샌드박스 등 조직 방화벽이 kobc.or.kr 접속을 막는 환경에서는
   requests 요청 자체가 거부된다 (반면 실제 브라우저로 여는 건 항상 가능).

실행:
  pip install requests pandas lxml
  python collect_kobc.py                       # kdci, kcci 둘 다, 2022-01-01 ~ 오늘
  python collect_kobc.py --since 2023-01-01 --target kdci
  python collect_kobc.py --out inbox           # run_monitor.py의 inbox/ 로 바로 저장

출력: kobc_kdci.csv, kobc_kcci.csv (Date + 지수 컬럼들)
"""
import argparse, datetime as dt, sys
from io import StringIO

import pandas as pd
import requests
import urllib3

# 회사망(자산운용사·증권사 등)은 보안 솔루션(Zscaler·사내 프록시 등)이 SSL을 가로채면서
# 자체 self-signed 인증서로 다시 서명하는 경우가 많다. 브라우저는 회사가 배포한 인증서를
# Windows 인증서 저장소에 심어놔서 문제없이 열리지만, requests(=Python)는 별도의
# 인증서 목록(certifi)만 신뢰하기 때문에 "self-signed certificate in certificate chain"
# 오류가 난다. 이 스크립트는 사내망에서 돌리는 걸 전제로 검증을 끈다.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False   # 회사 네트워크가 아니라 SSL 검증 오류가 안 나는 환경이면 True로 바꿔도 된다

TARGETS = {
    'kdci': dict(url='https://www.kobc.or.kr/ebz/shippinginfo/kdci/gridList.do?mId=0301000000',
                 mId='0301000000', sources='kdci', label='건화물선운임지수'),
    'kcci': dict(url='https://www.kobc.or.kr/ebz/shippinginfo/timeseries/gridList.do?mId=0304000000',
                 mId='0304000000', sources='kcci', label='컨테이너선운임지수'),
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.kobc.or.kr/',
}


def fetch(key: str, since: dt.date, until: dt.date) -> pd.DataFrame:
    t = TARGETS[key]
    data = {
        'sources': t['sources'], 'page': '1',
        'sDay': since.isoformat(), 'eDay': until.isoformat(),
        'siteCode': 'shippinginfo', 'mId': t['mId'],
    }
    r = requests.post(t['url'], data=data, headers=HEADERS, timeout=30, verify=VERIFY_SSL)
    r.raise_for_status()
    tables = pd.read_html(StringIO(r.text))
    if not tables:
        raise RuntimeError('표를 찾지 못함 (사이트 구조가 바뀌었을 수 있음)')
    df = max(tables, key=lambda d: d.shape[0])          # 가장 행이 많은 표 = 데이터 표
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={df.columns[0]: 'Date'})
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')
    if len(df) == 0:
        raise RuntimeError('빈 표 (검색 결과 없음 / No data)')
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2022-01-01')
    ap.add_argument('--target', default='all', choices=['all', *TARGETS])
    ap.add_argument('--out', default='.')
    a = ap.parse_args()

    since = dt.date.fromisoformat(a.since)
    until = dt.date.today()
    keys = list(TARGETS) if a.target == 'all' else [a.target]

    ok = 0
    for k in keys:
        t = TARGETS[k]
        try:
            df = fetch(k, since, until)
            out_path = f'{a.out}/kobc_{k}.csv'
            df.to_csv(out_path, index=False, encoding='utf-8-sig')
            print(f'[OK]   {t["label"]:14s} {len(df):5d}행 -> {out_path}  (최신 {df["Date"].max().date()})')
            ok += 1
        except requests.exceptions.RequestException as e:
            print(f'[실패] {t["label"]:14s} 네트워크 오류: {e!r}')
            print('       -> 이 PC/네트워크에서 kobc.or.kr 접속이 막혀 있을 수 있습니다.')
        except Exception as e:
            print(f'[실패] {t["label"]:14s} {e!r}')

    if ok == 0:
        return 1
    print('\nncfi(닝보)·kpli(항만물류)는 자동화 불안정 - 여전히 수기 확인 권장')
    return 0


if __name__ == '__main__':
    sys.exit(main())
