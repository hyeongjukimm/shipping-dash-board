-- 해운·물류 지표 대시보드 기초 DB (SQLite 기준, PostgreSQL 호환)
-- 원칙: 모든 시계열은 long format 한 테이블(observation)에 적재. 지표 메타는 indicator, 이벤트는 event.

CREATE TABLE IF NOT EXISTS indicator (
  code        TEXT PRIMARY KEY,   -- 예: KCCI, KDCI, KDCI_CAPE, KUWI, NCFI, SCFI, BDI, WCI, PW_PORT_SHANGHAI
  name_ko     TEXT NOT NULL,
  group_name  TEXT NOT NULL,      -- 건화물선 / 컨테이너 / 항만물류 / 물동량 / 원자재 / 금리 / 주가 / 환율
  unit        TEXT,               -- pt, $/FEU, $/day, TEU, %, ...
  freq        TEXT NOT NULL,      -- D / W / M
  source      TEXT NOT NULL,      -- KOBC / RESEARCH_DB / PORTWATCH / BLOOMBERG / NYFED / MANUAL
  source_ref  TEXT,               -- URL, dataset_code, Bloomberg ticker
  release_rule TEXT,              -- 예: 'MON 14:00 KST', 'D 17:00 KST', 'FRI'
  lag_days    INTEGER DEFAULT 0,  -- 소스 게시 지연(일)
  bbg_ticker  TEXT,
  description TEXT,
  usage_note  TEXT,               -- 활용도
  invest_note TEXT,               -- 투자 활용법
  active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS observation (
  code        TEXT NOT NULL REFERENCES indicator(code),
  obs_date    TEXT NOT NULL,      -- YYYY-MM-DD (주간지수는 발표 기준일)
  value       REAL,
  loaded_at   TEXT NOT NULL,      -- 적재 시각
  source_file TEXT,               -- 원본 파일명/URL (감사추적)
  PRIMARY KEY (code, obs_date)
);
CREATE INDEX IF NOT EXISTS ix_obs_date ON observation(obs_date);

CREATE TABLE IF NOT EXISTS event (
  event_id    TEXT PRIMARY KEY,   -- redsea_2023, suez_2021 ...
  event_date  TEXT NOT NULL,
  end_date    TEXT,
  name_ko     TEXT NOT NULL,
  shock_type  TEXT NOT NULL,      -- 공급제약(항로) / 공급제약(운하) / 항만폐쇄·파업 / 수요충격(정책) / 수요충격(경기) / 원자재 / 에너지
  region      TEXT,
  lat REAL, lon REAL,             -- 지도 표시용
  mechanism   TEXT,               -- 왜 지표가 움직였나
  market_reaction TEXT,           -- 지수·금리·환율 반응 요약
  outlook_note TEXT,              -- 당시 전망 vs 실제
  source_url  TEXT
);

-- 이벤트 윈도우 계산 결과 (build_dashboard_data.py가 재계산하여 덮어씀)
CREATE TABLE IF NOT EXISTS event_window (
  event_id TEXT REFERENCES event(event_id),
  code     TEXT REFERENCES indicator(code),
  base_value REAL,                -- T-1주 값
  chg_4w REAL, chg_8w REAL, chg_12w REAL, chg_26w REAL,
  max_26w REAL, min_26w REAL,     -- 26주 내 최대/최소 변화율(%)
  weeks_to_peak INTEGER,
  PRIMARY KEY (event_id, code)
);

-- 해진공 보고서·시황 코멘트 (변화 이유·전망 패널)
CREATE TABLE IF NOT EXISTS commentary (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  pub_date    TEXT NOT NULL,
  source      TEXT NOT NULL,      -- KOBC_DAILY / KOBC_WEEKLY / KOBC_QUARTERLY / NCFI_WEEKLY / TEAM
  title       TEXT,
  url         TEXT,
  related_codes TEXT,             -- 'KDCI,KDCI_CAPE'
  summary     TEXT,               -- 3줄 요약 (LLM 또는 수기)
  outlook     TEXT                -- 전망 문단
);

-- 지표 ↔ 관련 자산 매핑 (연관 기업·섹터·원자재·채권 패널)
CREATE TABLE IF NOT EXISTS related_asset (
  code        TEXT REFERENCES indicator(code),
  asset_ticker TEXT NOT NULL,     -- 011200 KS, MAERSKB DC, SCO1 Comdty, USGG10YR Index
  asset_name  TEXT,
  asset_type  TEXT,               -- 기업 / 섹터 / 원자재 / 채권 / 환율
  direction   TEXT,               -- + (동행) / - (역행) / ± (조건부)
  logic       TEXT,               -- 연결 논리 한 줄
  PRIMARY KEY (code, asset_ticker)
);

-- 지도용 항만·초크포인트 마스터
CREATE TABLE IF NOT EXISTS port (
  port_id     TEXT PRIMARY KEY,   -- portwatch id 또는 UN/LOCODE (CNSHG, SGSIN ...)
  name        TEXT NOT NULL,
  country     TEXT,
  kind        TEXT,               -- port / chokepoint
  lat REAL NOT NULL, lon REAL NOT NULL,
  kpli_code   TEXT,               -- 해진공 항만코드 (cnshg, aejea, ...)
  teu_annual  REAL                -- 최근 연간 처리량(백만 TEU), 참고
);

-- 수집 로그 (실패 감지·재시도)
CREATE TABLE IF NOT EXISTS load_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TEXT, job TEXT, status TEXT, rows_loaded INTEGER, message TEXT
);
