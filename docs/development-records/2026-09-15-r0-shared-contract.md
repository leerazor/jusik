# R0-02 시장 연구 자료 계약

- 상태: 검증
- 기록 시각: 2026-09-15T03:06:42Z
- 작업 slug: `r0-shared-contract`
- 기준/통합: `935a31e3400e2aab445b6146fea71b0adde91598` / 없음
- 범위: 연구 결과에 snapshot 기반 provenance를 선택적으로 노출하고 Python·Zod의 legacy 호환 계약을 문서화했습니다. Dataset/snapshot schema, snapshot hash, 기존 data contract hash와 gate, 전략 계산·금융 수치는 보존했습니다.

## 변경과 결정

- `MarketResearchProvenance` (`backend/jusik/market_history_models.py`)를 추가했습니다. membership·bar·FX·raw artifact의 실제 source identity 배열, normalization version, snapshot `captured_at`만 담으며 API에 절대 경로·원문·자격증명을 노출하지 않습니다.
- `MarketResearchService` (`backend/jusik/market_research_service.py`)가 실행 결과에 snapshot provenance를 주입합니다. 빈 source는 source를 추정하지 않고 각 값을 `null`로 남기며, 실제 snapshot/artifact가 없으면 capture 시각도 `null`입니다. 기존 result의 provenance 누락은 `None`으로 읽습니다.
- `frontend/lib/marketResearch.ts`에 같은 provenance Zod schema와 타입을 추가하고, 새 필드를 `optional().nullable()`로 두어 기존 저장 결과와 호환합니다.
- `docs/market-research-contract.md`에 필드·단위·기본값·unknown 정책, UTC availability/capture/execution semantics, raw row와 계산 coverage 차이, run status/error/result 관계 및 private audit 경계를 기록했습니다.
- fixture API와 저장 legacy fixture 검증을 확장해 source identity·normalization·capture 전달, 빈 source unknown, 기존 금융/trades/equity/grade gate 보존을 확인했습니다.
- provenance metadata의 private boundary를 기존 artifact retrieval route와 구분하고, Zod에서 1~40자 normalization version과 timezone offset ISO capture timestamp를 검증하는 영구 fixture script를 추가했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research-contract.md`를 새 API 데이터 계약의 authoritative 문서로 추가했습니다.
- 운영 문서: 해당 없음. private audit 경계만 계약에 명시했으며 운영 경로는 변경하지 않았습니다.
- API·설정·데이터 계약: 결과에 optional `provenance` 필드를 additive하게 추가했습니다. 기존 `input_hash`, `policy_hash`, `data_contract_hash`, `pool_contract_hash` 계산과 request/result gate는 변경하지 않았습니다.

## 검증

- `python3.13 -m venv backend/.venv && backend/.venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.lock` — 통과; 워크트리 전용 Python 3.13 환경과 lock 의존성을 사용했습니다.
- `cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_market_research.py tests/test_market_history_approximate.py` — 통과; 46개 테스트, deprecation warning 2개.
- `backend/.venv/bin/ruff format --check ... && backend/.venv/bin/ruff check ...` — 통과; 변경 Python 3개 파일.
- `backend/.venv/bin/python -m mypy --strict jusik/market_history_models.py jusik/market_research_service.py` — 통과.
- `npm run verify:market-research-contract` (`tsx` 4.23.13 고정) — 통과; current와 provenance 누락 legacy run을 파싱하고 빈 normalization version·timezone 없는 capture timestamp를 거부했습니다.
- `npm ci --no-audit --no-fund`, `npm run lint`, `npm run typecheck`, `npm run build` — 통과; Next.js production build 완료. npm deprecated/install-script 경고는 실패가 아닙니다.
- 실행하지 않은 검사: 전체 backend pytest와 독립 review. 통합 전 supervisor가 전체 영향 범위를 재검증해야 합니다.

## 안전·운영 상태

- 테스트는 fixture·임시 DB만 사용했으며 운영 DB·서비스·runner·provider 호출·실주문·원격 push는 수행하지 않았습니다.
- 비밀정보·자격증명·인증 응답·계좌 식별자는 기록하거나 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-shared-contract`; manifest: `r0-shared-contract-verification.json`; SHA-256: `07e46296228238bde9fceb2e40400c7a03473b6d64d031929c86f11cceb93c1a`.
- 남은 작업·차단 조건: supervisor 독립 review와 local `main` 통합 검증 전까지 완료로 표시하지 않습니다. R0-04 통화 metadata와 R0-05 grade label은 후속 작업입니다.
- 다음 시작: supervisor가 이 브랜치의 diff와 contract 문서를 검토한 뒤 전체 backend 영향 테스트와 통합 검증을 수행합니다.
