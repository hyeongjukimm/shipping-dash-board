# -*- coding: utf-8 -*-
"""
해운·물류 지표 모니터 — 한 번에 실행하고 브라우저로 열기

  python run_monitor.py                         inbox/ 의 가장 최근 bbg_*.xlsx 사용
  python run_monitor.py bbg_20260911.xlsx       파일 직접 지정
  python run_monitor.py --public                공표용을 연다 (기본은 내부용)
  python run_monitor.py --no-open               파일만 만들고 열지 않음

처음 한 번:  pip install pandas openpyxl
결과물:      output/dashboard_내부검토용.html , output/dashboard_외부공표용.html
"""
import sys, pathlib, webbrowser, traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'render'))

def latest_xlsx():
    cands = []
    for d in (HERE / 'inbox', HERE, HERE.parent):
        if d.is_dir():
            cands += [p for p in d.glob('bbg*.xls*')
                      if not p.name.startswith('~$') and 'template' not in p.name.lower()]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    xlsx = pathlib.Path(args[0]) if args else latest_xlsx()

    if xlsx and not xlsx.exists():
        print(f'[!] 파일을 찾을 수 없습니다: {xlsx}'); return 1
    print('해운·물류 지표 모니터 빌드')
    print(f'  Bloomberg 파일: {xlsx if xlsx else "없음 — 기준 데이터(센터DB·NOAA·FAO)만으로 생성"}')

    try:
        import pandas, openpyxl   # noqa
    except ImportError:
        print('[!] pandas / openpyxl 이 필요합니다:  pip install pandas openpyxl'); return 1

    try:
        import build
        made = build.main(str(xlsx) if xlsx else None)
    except Exception:
        traceback.print_exc()
        print('\n[!] 빌드 실패. 위 오류를 알려주시면 수정하겠습니다.'); return 1

    for p in made: print(f'  생성: {p}')
    if '--no-open' not in flags:
        target = made[1] if '--public' in flags else made[0]
        webbrowser.open(target.resolve().as_uri())
        print(f'  브라우저로 열기: {target.name}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
