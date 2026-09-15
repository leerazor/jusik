# R0-05 연구 등급·자료 성격 표시 계약

- 상태: 검증
- 기록 시각: 2026-09-15T03:53:41Z
- 작업 slug: `r0-grade-contract`
- 기준/통합: `7ea9825ff702414db7cd6707eb6b5ff212f79b0b` / 없음
- 범위: 시장 연구 목록·상세 화면에서 strict/approximate 등급, 합성/원천 자료 성격, 시뮬레이션 연구와 별도 PAPER를 구분해 표시했습니다. API enum·backend·전략·계산은 변경하지 않았습니다.

## 변경과 결정

- `frontend/lib/marketResearch.ts`에 grade/source/execution 표시 helper를 추가했습니다. `readiness.simulated`는 source 성격으로만 표시하고 `research_grade`와 섞지 않습니다.
- 시장 readiness 목록은 `엄격한 PIT 등급`·`근사 등급`, `원천 자료`·`합성 자료`, `준비됨`·`자료 확인 불충분`을 함께 표시합니다. 불충분 원천 자료를 strict 검증 완료로 표시하지 않습니다.
- 시장 상세는 확인된 결과에 `시뮬레이션 연구 실행 · PAPER 별도`를 표시하고, 결과가 없거나 오류이면 자료 성격·실행 결과 확인 불가로 표시합니다.
- 상세의 `result=null`은 queued/running 대기, failed 안전한 일반 실패, completed/legacy 결과 확인 불가로 구분하며 원시 오류를 렌더링하지 않습니다.
- 영구 fixture가 strict/approximate와 synthetic/non-synthetic, partial/failed/empty legacy 상태의 표시 규칙을 확인합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research-contract.md`에 등급·자료 성격·실행 표시 표를 추가했습니다.
- 운영 문서: 해당 없음. PAPER API와 실행 설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 기존 `strict`·`approximate` enum과 readiness/result schema를 유지하고 frontend 표시 helper만 추가했습니다.

## 검증

- `npm ci --no-audit --no-fund` — 통과; worktree 전용 frontend 의존성을 lock으로 설치했습니다.
- `cd frontend && npm run verify:market-research-contract && npm run lint && npm run typecheck && npm run build` — 통과; strict/approximate와 synthetic/non-synthetic, partial/failed/empty legacy 및 null-result heading을 검증했습니다.
- browser smoke — 실행하지 않음; API 호출 없이 계약 fixture·production build로 표시 규칙을 검증했습니다.

## 안전·운영 상태

- local fixture와 frontend build만 사용했습니다. 운영 API·DB·provider 호출·PAPER 상태·실주문·원격 push는 수행하지 않았습니다.
- 비밀정보·자격증명·계좌 식별자는 기록하거나 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-grade-contract`; manifest: `r0-grade-contract-verification.json`; SHA-256: `d34c101ce7daf1e38cc510977a86c339470973b761a646ef4636f75feae5e2d1`.
- 남은 작업·차단 조건: supervisor 독립 review와 local `main` 통합 전입니다. R0-03은 후속 작업입니다.
- 다음 시작: supervisor가 helper label과 목록·상세 소비 위치를 검토합니다.
