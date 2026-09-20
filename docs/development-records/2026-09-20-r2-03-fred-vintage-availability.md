# R2-03 FRED vintage availability bound

- 상태: 기술 parser 보강·historical PIT/economic acceptance 미완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r2-03-fred-vintage-availability-20260920`
- 기준/통합: `33a2804` / 통합 예정
- 범위: FRED JSON의 `realtime_start` vintage 날짜를 FX row의 보수적 availability upper bound로 반영했습니다. 기존 caller가 `available_at`을 명시하면 그 값을 우선하며, vintage가 없는 legacy 응답은 기존 session+1일 fallback을 유지합니다.

## 변경과 결정

- `parse_fred_observations()`는 `realtime_start` 다음 UTC 자정을 availability로 사용합니다. FRED 필드는 intraday publication 시각이 아니므로 당일 사용 가능하다고 추정하지 않습니다.
- canonical 경계 4개를 FRED vintage API로 bounded 조회했습니다.
  - `2025-09-11`: value `1388.97`, realtime start `2025-09-15`
  - `2025-10-13`: missing value(`.`), realtime start `2025-10-20`
  - `2025-11-11`: missing value(`.`), realtime start `2025-11-17`
  - `2026-04-03`: value `1510.17`, realtime start `2026-04-06`
- 관측 가능일이 거래일 이후이므로 이 자료만으로 R2-03 NAV/Sharpe를 승격하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 기존 approximate/strict 등급과 fail-closed readiness는 유지합니다.
- 운영 문서: `docs/worktree-tasks.md`에 parser와 vintage evidence를 등록합니다.
- API·설정·데이터 계약: FRED JSON parser의 optional `realtime_start` 처리만 확장했습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py -q` — `141 passed`.
- Ruff, strict mypy(`market_data_collector.py`), `git diff --check` — 통과.
- vintage boundary summary SHA-256: `c0a324f33297ca31983c34fa9565ba4190ebe91d89b5b2825db6a23489c8cde8`.

## 안전·운영 상태

- 실주문·PAPER/live 승격·remote push·Windows 종료를 수행하지 않았습니다.
- raw/vintage 자료는 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-vintage-probe/`에만 저장했습니다.

## 증거와 재개

- 남은 작업·차단 조건: canonical 전체 기간의 vintage coverage와 거래 시점 이전 availability, KOFR·비용 계약이 필요합니다.
- 다음 시작: 전체 canonical FX 기간에 대해 bounded vintage coverage를 계산하거나 SEC action review를 진행합니다.
