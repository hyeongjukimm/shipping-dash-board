해운·물류 지표 모니터 — 빠른 시작
====================================

1. 최초 1회
   pip install pandas openpyxl requests lxml

2. Bloomberg 터미널 PC에서
   bbg_template_v4.xlsx 열기 → Refresh All → 다른 이름으로 저장
   → bbg_YYYYMMDD.xlsx 로 inbox/ 폴더에 저장

2-1. 해진공 KDCI·KCCI 자동 갱신 (선택, 인터넷만 되면 어디서든 가능)
   python collect_kobc.py --out inbox
   → inbox/kobc_kdci.csv, kobc_kcci.csv 생성. run_monitor.py 가 자동으로 읽어서
     대시보드의 KDCI_M/KCCI_M 카드·차트를 실측값으로 채웁니다.
   (NCFI·KPLI는 사이트 구조상 자동화가 불안정해 계속 수기 확인 권장)

3. 실행 (이 폴더에서)
   python run_monitor.py

   → inbox/ 의 최신 bbg_*.xlsx 를 읽어 국면 판정까지 계산하고
     output/ 에 대시보드 HTML 2종을 만든 뒤 내부용을 브라우저로 엽니다.

   옵션
     python run_monitor.py bbg_20260911.xlsx   파일 직접 지정
     python run_monitor.py --public            공표용을 연다
     python run_monitor.py --no-open           파일만 생성

   Bloomberg 파일이 없어도 실행됩니다(기준 데이터만으로 생성).

4. 결과물
   output/dashboard_내부검토용.html   국면판단·지도·지표보드·충격사례·연결지수·관련자산·코멘트
   output/dashboard_외부공표용.html   투자활용법·관련자산·기업주가 제외

   두 파일 모두 라이브러리 내장 — 인터넷 없이 더블클릭으로 열립니다.
   공유폴더에 두면 팀원 누구나 열 수 있습니다.

5. 자동화 (선택)
   Windows 작업 스케줄러에 "매일 17:30 → python run_monitor.py --no-open" 등록.
   해진공·PortWatch 자동수집까지 붙이려면 run_all.py 참조.

6. 해진공 부분을 클라우드에서 매일 자동으로 (선택, GitHub 필요)
   블룸버그는 터미널 라이선스가 PC에 묶여 있어 클라우드 자동화가 불가능하지만,
   해진공(KDCI·KCCI)은 requests만 있으면 되므로 GitHub Actions로 대신 돌릴 수 있다.

   설정 (최초 1회):
   a) GitHub에 새 저장소(비공개 가능)를 만들고, 이 폴더(pipeline/) 안의
      내용물을 그 저장소의 "루트"로 그대로 push한다.
      (.github/workflows/kobc_daily.yml 이 이미 이 폴더 안에 올바른 위치로
       들어있으므로, 폴더 이름을 바꾸거나 한 겹 더 감쌀 필요 없이
       "이 폴더 안의 파일들"을 저장소 루트에 그대로 올리면 된다)
   b) 저장소 Settings → Actions → General → Workflow permissions를
      "Read and write permissions"로 바꾼다 (봇이 커밋·푸시하려면 필요).
   c) Actions 탭에서 "KOBC KDCI·KCCI 일일 자동 수집" 워크플로우를 한 번
      수동 실행(Run workflow)해서 정상 동작하는지 확인한다.

   그 다음부터는 평일 새벽(KST 06:30)에 자동으로 inbox/kobc_*.csv 가
   갱신되어 저장소에 커밋된다. 실제 대시보드를 만들 때는:
        git pull
        python run_monitor.py
   두 줄이면 되고, 해진공 데이터는 항상 그날 새벽 기준 최신 상태다.

   ※ kobc.or.kr 접속이 막힌 사내망에서 GitHub Actions를 돌리는 게 아니라
   GitHub의 클라우드 러너에서 돌기 때문에 접속 자체는 문제없이 될 가능성이 높다.
   다만 사이트 구조가 바뀌면(폼 필드명 등) collect_kobc.py 자체를 손봐야 한다 —
   이 스크립트는 2026-09-11 기준 사이트 구조로 만들어졌다.

7. 대시보드 자체도 매일 자동으로 "링크"로 공개 (선택, GitHub Pages)
   6번까지 설정했다면, kobc_daily.yml 워크플로우가 해진공 수집 직후
   python run_monitor.py --no-open 까지 실행해서 대시보드 HTML을 만들고
   GitHub Pages에 자동 배포하도록 이미 구성되어 있다. 즉 파일을 받을 필요 없이
   브라우저로 링크 하나만 열면 그날 새벽 기준 최신 대시보드가 보인다.

   설정 (최초 1회, 6번 이후):
   a) 저장소 Settings → Pages → Build and deployment → Source를
      "GitHub Actions"로 지정한다.
   b) Actions 탭에서 워크플로우를 한 번 수동 실행(Run workflow)하면
      Settings → Pages 에 사이트 URL(예: https://<계정>.github.io/<저장소>/)이 뜬다.
   c) 그 링크를 열면 내부 검토용 / 외부 공표용 두 링크가 뜨는 랜딩 페이지가 보인다.

   ※ 한계 1 — 블룸버그: 이 자동 배포는 저장소 inbox/ 안에 "커밋되어 있는"
   bbg_*.xlsx 파일만 사용한다. 로컬에서 Refresh All → inbox/ 저장 후
        git add inbox/bbg_YYYYMMDD.xlsx && git commit -m "bbg 갱신" && git push
   로 직접 올려줘야 다음 야간 배포부터 블룸버그 수치가 반영된다. 올리지 않으면
   센터DB·NOAA·FAO 기준 데이터 + 해진공 KDCI·KCCI만 반영된 채로 배포된다.

   ※ 한계 2 — 공개 범위 (중요): 저장소가 Public이면 GitHub Pages도 항상 Public이라
   "내부 검토용" 대시보드까지 인터넷에 그대로 노출된다. 저장소를 Private로 두면
   Pages도 비공개로 유지되지만, 이는 GitHub Team/Enterprise 요금제에서만 지원되는
   기능이다(일반 Private 저장소의 무료 Pages는 조직 설정에 따라 다를 수 있으니
   Settings → Pages 화면에서 "Private" 옵션이 보이는지 먼저 확인할 것). 사내 정책상
   블룸버그·내부 리서치 수치를 외부에 노출할 수 없다면, 이 7번 단계는 건너뛰고
   6번(해진공 자동 수집)까지만 쓰거나, 접근 제어가 되는 사내 사이트에 output/ 폴더를
   올리는 방식으로 대체해야 한다.

폴더 구조
   run_monitor.py                       실행 진입점
   render/build.py                      엑셀 → 국면판정 → HTML 생성
   render/dash_conf.json                지표 설명·항만·초크포인트·관련자산 설정 (문구 수정은 여기)
   render/base_data.json                센터DB·NOAA ONI·FAO 기준 시계열 + 충격사례 마스터
   inbox/                               Bloomberg 엑셀 + collect_kobc.py 결과 CSV를 넣는 곳
   output/                              생성된 대시보드
   collect_kobc.py                      해진공 KDCI·KCCI 자동수집 (requests 기반, 브라우저 불필요)
   .github/workflows/kobc_daily.yml     collect_kobc.py를 GitHub Actions로 매일 자동 실행
                                         (저장소 루트의 .github/workflows/ 로 옮겨서 사용)
