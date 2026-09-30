# ECOS·FRED 원/달러 진단 비교

- 상태: 완료; 진단 도구·실제 소량 조회 검증, 성과 적용은 미승격
- 기록 시각: 2026-09-30T04:13:44Z
- 작업 slug: `ecos-fx-comparison-20260930`
- 기준/통합: `6e964ca2b9a2fec15523e6320b6d074a39725a7c` / `e9cf0a44645269d83ad78a58e26d5f2741af342f`
- 범위: 고정 FRED CSV와 ECOS 공개 sample 응답의 최대 10일 진단 대조만 추가. 성과·전략·운영 입력은 그대로 보존.

## 변경과 결정

- `backend/jusik/research_ecos_fx_comparison.py`: 해시로 고정한 CSV를 조회 전 검증하고, 날짜마다 고정 HTTPS sample endpoint를 한 번 조회한다. 성공 원문과 해시·조회시각, 명시적 결측·부재·실패 및 Decimal 차이를 새 출력 디렉터리에 기록한다.
- 기존 `parse_fred_csv_observations`는 명시적 결측 행을 버리고 전체 값이 없으면 예외를 발생시키므로, 진단에 필요한 결측·부재 구분을 위해 별도 작은 CSV 파서를 사용했다. 헤더·중복·유효 환율 검사는 동일하게 실패 폐쇄 방식이다.
- `backend/tests/test_research_ecos_fx_comparison.py`: MockTransport로 identity, 실패, 결측, 해시, 입력 불변성과 조회 전 차단을 검증한다.
- 독립 검토 지적에 따라 극단적인 Decimal 지수의 baseline은 조회 전 거절하고 ECOS 값·차이 계산 실패는 해당 날짜 오류로 격리한다. `fetched_at`은 성공 본문 수신 후에 기록하며 실패에는 `null`을 둔다.

## 문서·계약 영향

- 사용자 문서: `docs/ecos-fx-comparison.md`에 범위·실행법·진단 한계를 명시하고 `docs/market-research.md`에서 연결했다.
- 운영 문서: 기존 실행기·서비스 절차 변경 없음.
- API·설정·데이터 계약: 독립 CLI·보고서 `ecos-fx-diagnostic-v1`만 추가. 인증값, DB, cache, 전략, readiness 계약 변경 없음.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_research_ecos_fx_comparison.py backend/tests/test_market_data_collector.py -q` — 182개 통과.
- `backend/.venv/bin/ruff check backend/jusik/research_ecos_fx_comparison.py backend/tests/test_research_ecos_fx_comparison.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/research_ecos_fx_comparison.py backend/tests/test_research_ecos_fx_comparison.py` — 통과.
- `backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/jusik/research_ecos_fx_comparison.py backend/tests/test_research_ecos_fx_comparison.py` — strict 통과.
- 고정 실제 CSV는 읽기 전용 로컬 검사에서 262개 날짜를 파싱했고, 2025-09-11은 1388.97, 2025-10-13은 명시적 결측으로 확인했다. 조회·출력은 하지 않았다.
- 실행하지 않은 검사: 실제 ECOS sample 조회 4회 모두 성공했다. Python CLI에 별도 빌드 대상은 없다.

## 안전·운영 상태

- PAPER·실주문 없음. 서비스·DB·cache·기존 CSV·배포·원격 push 변경 없음. 인증값 입력이나 로깅 없음.

## 증거와 재개

- 고정 baseline: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-csv-evidence/DEXKOUS-2025-09-11-2026-09-11.csv`; SHA-256 `06751750c69089e33aaac8d5bdd0e102887c9c4db2d4d5da529561ad318f8210`. 기존 파일은 읽기만 했다.
- 남은 작업·차단 조건: 요청한 진단 적용은 완료. 역사적 공표시각·수정 이력과 원천 간 환율 기준의 적용 계약은 미확인이므로 기존 NAV·readiness·성과 입력으로 승격하지 않는다.
- 다음 시작: 사용 문서와 실제 comparison.json을 읽고, 과거 성과 입력이 필요한 경우 공표시점·환율 기준 계약을 먼저 확인한다.

## 통합·실제 조회 확인 (2026-09-30T04:17:52.171075+00:00)

- 구현 커밋 `71346ed5467074ff468c6476044e594d1156a036`, main 통합 `e9cf0a44645269d83ad78a58e26d5f2741af342f`.
- 독립 review에서 극단 Decimal 값의 전체 중단과 조회 전 fetched_at을 발견해 같은 구현자가 수정했다. 재검토 PASS, 독립 테스트 33개 통과.
- main 통합 후 새 진단·기존 collector pytest **182개 통과**, Ruff check/format, strict mypy(코드·테스트), diff check 통과. 전체 서비스 suite는 독립 진단 CLI 범위에 불필요하여 실행하지 않았다.
- 실제 조회는 고정 4날짜 각각 1회, 재시도 없이 수행했다.

| 날짜 | FRED (원/USD) | ECOS (원/USD) | ECOS − FRED |
| --- | ---: | ---: | ---: |
| 2025-09-11 | 1388.97 | 1387.6 | -1.37 |
| 2025-10-13 | 명시적 결측 | 1420.5 | 계산 불가 |
| 2025-11-11 | 명시적 결측 | 1453.7 | 계산 불가 |
| 2026-04-03 | 1510.17 | 1518.8 | 8.63 |

- 두 환율의 고시 기준은 다르므로 차이를 정확성·성과의 우열로 해석하지 않는다. 결측 두 날짜는 원천 후보를 확보했으며 기존 FRED 파일은 그대로다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-ecos-fx-comparison`; `live/comparison.json` SHA-256 `a9140a8b6ecf30409b070ef8004b0765baad4fff49457e0dc4831e217b363634`. 성공 원문 4개의 해시는 `live-verification.json`으로 확인했다.
- `integration-verification.json`에 통합 커밋·검사·코드 SHA를, `worker-requirements.txt`와 `main-requirements.txt`에 재현 환경을 보존했다. baseline·연구 mandate SHA 불변도 확인했다.
- runner는 시작 전부터 paused=true, service/timer inactive였고 종료 시도 같은 상태를 유지한다. 수동 작업 절차의 pause/stop을 확인했으며 자동 resume은 하지 않는다.
- 작업 워크트리 `/home/kwl/projects/jusik-ecos-fx-comparison`와 통합된 브랜치를 정리했다. 기존 사용자 `HANDOFF.md`는 보존했다.
- 새 인계: `docs/handoffs/2026-09-30-ecos-fx-comparison.md`.
