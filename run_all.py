# -*- coding: utf-8 -*-
"""
스케줄 러너 — 지표 발표 시각에 맞춰 잡을 실행한다 (Windows 작업 스케줄러 / cron에서 매시간 호출).
  KST 기준
  - 매일 17:30  : KDCI(일별), PortWatch, Bloomberg inbox, research DB, 대시보드 빌드
  - 월요일 14:30: KCCI(월 14:00 발표) → 즉시 반영
  - 월요일 10:00: NCFI(금요일 발표분, 해진공 익주 게시)
  - 매주 화 09:00: KPLI(시험발간 → 정식 발간 후 주기 확정)
  - 매월 5일 09:00: GSCPI 등 월간
실행: python run_all.py            (현재 시각에 해당하는 잡만)
      python run_all.py --force all (전체 강제)
"""
import argparse, datetime as dt, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).parent
PY = sys.executable

def run(*args):
    print('>>', ' '.join(args)); subprocess.run([PY, *args], cwd=HERE)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--force', default=None); a = ap.parse_args()
    now = dt.datetime.now(); wd, hh = now.weekday(), now.hour
    jobs = []
    if a.force == 'all' or hh == 17:
        jobs += [('collect_kobc.py', '--target', 'kdci'), ('collect_portwatch.py',), ('ingest_bloomberg.py',), ('ingest_research_db.py',)]
    if a.force == 'all' or (wd == 0 and hh == 14):
        jobs += [('collect_kobc.py', '--target', 'kcci')]
    if a.force == 'all' or (wd == 0 and hh == 10):
        jobs += [('collect_kobc.py', '--target', 'ncfi')]
    if a.force == 'all' or (wd == 1 and hh == 9):
        jobs += [('collect_kobc.py', '--target', 'kpli')]
    if a.force and a.force != 'all':
        jobs = [(a.force,)]
    for j in jobs: run(*j)
    if jobs: run('build_dashboard_data.py')

if __name__ == '__main__':
    main()
