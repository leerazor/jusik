# 무료 시장 데이터 수집기

- 상태: 완료
- 기록 시각: 2026-09-14T23:56:16Z
- 작업 slug: `free-market-data-collector`
- 기준/통합: `f15a3ffcbedc0355e406277acac2ef4b4d994a06` / `1407d71fe5b4327b8e81c0429a38055e63f30bd0` (`main` 완료 문서 `85212682b6f7fc9321954289dcf75a63c7d78330`)
- 범위: 무료·공개 원천에서 approximate 연구용 과거 시장 자료를 수집하는 CLI, 비밀정보 없는 cache, checkpoint/resume, prepared output 검증을 추가했습니다. PAPER·실주문·broker·프런트 동작은 보존했습니다.

## 변경과 결정

- `backend/jusik/market_data_collector.py`가 KRX·Alpha Vantage·Yahoo·FRED adapter, 시간 인과성, request budget, cache hash와 완료 marker를 담당합니다.
- `backend/jusik/market_research_cli.py`에 `collect`, `collect-status`를 추가하고 기존 `import-file`, `backfill` 호환성을 유지했습니다.
- 한국 자료는 날짜별 KRX KOSPI·KOSDAQ 일별매매정보만 사용합니다. 상장주식 수 변화·거래행 누락·종목 소멸 이후 자료는 제외하며 조정 가격을 만들지 않습니다.
- 미국 표본은 기간 시작 시점 historical Alpha Vantage listing으로 고정합니다. Yahoo 가격과 세션 전 이용 가능 FRED 환율을 사용하며, 후속 checkpoint를 과거에 소급하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 변경 없음. 실제 provider 자료가 없어서 성과나 준비 완료를 표시하지 않았습니다.
- 운영 문서: `docs/worktree-tasks.md`에 완료 상태·검증·재개 조건을 반영했습니다.
- API·설정·데이터 계약: `KRX_AUTH_KEY`, `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`가 있어야 실제 수집을 시작합니다. 값은 문서·기록에 저장하지 않습니다.

## 검증

- collector·approximate·market research·API·mandate 통합 pytest 104개 — 통과. 기존 Starlette/httpx deprecation warning 2건.
- Ruff, strict mypy 8개 source, `git diff --check` — 통과.
- 독립 review — 최종 P1/P2 없음. KRX 요청, KR/US 수집부터 loader/strategy까지, 미래 checkpoint, 기업행사 proxy, 사전 관측 환율, 429/예산, 손상 cache·marker를 probe했습니다.
- 자격증명 없는 CLI smoke — exit 2, ready false, 기존 prepared output 보존.
- 실제 provider smoke·1년 수익률 — 키와 KRX 서비스 승인이 없어 실행하지 않았습니다.

## 안전·운영 상태

- 전용 worktree는 제거했고 `feat/free-market-data-collector` branch는 보존했습니다.
- 자동 development runner service/timer는 inactive입니다. 원격 push·실제 주문·PAPER 변경 없음.
- 첫 ngrok 인증 probe 실패는 제품 변경 없이 재시작해 복구했고, local/API 200과 외부 비인증 401을 확인했습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-free-market-data-collector/HANDOFF.md`.
- 남은 작업·차단 조건: KRX KOSPI·KOSDAQ 일별매매정보 이용 승인과 세 API key가 필요합니다.
- 다음 시작: 키와 승인 여부를 확인한 뒤 2~3종목·짧은 기간의 KR/US `collect` smoke를 실행하고, 응답·quota를 검증한 다음 1년 prepared file을 생성합니다.
