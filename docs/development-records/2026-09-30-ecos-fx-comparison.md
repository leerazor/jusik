# ECOS·FRED 원/달러 진단 비교

- 상태: 구현 완료, 독립 검토·통합 대기
- 기록 시각: 2026-09-30T04:13:44Z
- 작업 slug: `ecos-fx-comparison-20260930`
- 기준/통합: `6e964ca2b9a2fec15523e6320b6d074a39725a7c` / 없음
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
- 실행하지 않은 검사: 실제 ECOS 조회는 감독자의 별도 소량 smoke 단계로 남겼다. Python CLI에 별도 빌드 대상은 없다.

## 안전·운영 상태

- PAPER·실주문 없음. 서비스·DB·cache·기존 CSV·배포·원격 push 변경 없음. 인증값 입력이나 로깅 없음.

## 증거와 재개

- 고정 baseline: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-csv-evidence/DEXKOUS-2025-09-11-2026-09-11.csv`; SHA-256 `06751750c69089e33aaac8d5bdd0e102887c9c4db2d4d5da529561ad318f8210`. 기존 파일은 읽기만 했다.
- 남은 작업·차단 조건: 독립 검토, 실제 sample 소량 smoke, main 통합 및 통합 검사.
- 다음 시작: 이 브랜치 변경과 집중 검사 근거를 독립 검토한 뒤 감독자가 소량 조회와 통합을 진행한다.
