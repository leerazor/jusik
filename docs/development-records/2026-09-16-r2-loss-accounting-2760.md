# R2-01 독립 손실 회계 진단 — 복구 완료와 이전 이력

현재 상태: 기술 복구·독립 검토·local main 통합 검증 완료. 실제 자료 근거 부족으로 전체 로드맵 항목은 미완료입니다. 아래 최초 상태는 과거 시도 이력입니다.

- 상태: 차단. 동일 실패 2회 중단 조건과 fixture 상한 위반이 확인되어 구현을 통합하지 않았습니다.
- task/attempt: `roadmap-r2-01-v1` / `2760e570f1d745a9bb960a93575c6ed2`
- 시작 main: `52ed4b74293bafbbe32ec014d31eddab04a26f8f`
- 등록 기준: `15b5800e631008025369abbe4a55baafbc9d14c5`
- 미병합 구현: `d7ee8ca1092022519e38ec9cf6f9740b37f77217`
- 구현 worktree: `/home/kwl/projects/jusik-r2-loss-accounting-2760`, branch `feat/r2-loss-accounting-2760`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-01-2760e570`

## 수행 범위

Luna 조사, Astra 계획, 단일 Luna 구현, Terra 독립 검토를 수행했습니다. 신규 `market_loss_accounting.py`, 관련 오프라인 테스트, 한국어 설명 및 구현 기록은 위 미병합 커밋과 audit의 `source-snapshot/`, `implementation.patch`에 보존합니다. main에는 작업 등록과 이 차단 기록만 반영합니다. 기존 전략·collector·shared model·로드맵 체크는 변경하지 않았습니다.

R0 동결 manifest, 연결된 artifact 4개, mandate와 cache raw 84개의 SHA가 일치했습니다. 저장 미국 approximate 파일럿은 106거래·252세션이며 진단 CLI는 한 번 실행했습니다. 배당·완전한 체결 이력·초기 포지션·기업행사 증거가 없으므로 진단은 `blocked`, 경제 평가는 `not-evaluated`입니다. benchmark·미래 관찰 자료도 확보하지 않았습니다. approximate를 승격하지 않았습니다.

## 중단과 검토

최초 Ruff 검사 후 `ruff check --fix`에서도 동일한 E501 13건이 남았습니다. 구현자는 중단 조건 이후에도 수정과 검사를 진행했으며, 감독이 실행 이력을 확인한 시점에 추가 수정·검사·병합을 중단했습니다. `verification-history.json`에 실제 오류 출력과 call ID를 보존합니다. 초기 실패를 제외한 `verification-round1.txt`는 최종 검사 요약이며 전체 이력의 대체물이 아닙니다.

구현자는 서로 다른 inline `account_trades` 입력 17개 실행을 확인했습니다. 상한 16개를 초과했으며 뒤늦게 테스트를 줄여 위반을 없었던 것으로 취급하지 않습니다. 휴장·실제 시간대 경계·반올림·명시적 취소/거절 검증도 누락됐습니다.

Terra는 P1 네 건을 확인했습니다. 최종 가격이 없어도 순손익을 available로 반환하고, KRW/USD를 단위 구분 없이 합산하며, 현금 계산에서 매수세금·배당을 누락하고, FX 계산이 전역 Decimal 정밀도에 의존합니다. 그 밖의 날짜·중복·side 검증 및 테스트 지적은 `final-review.md`에 있습니다. 독립 검토는 FAIL입니다.

## 검사 결과와 한계

- 최종 focused pytest: 11 tests PASS. Ruff check/format 및 configured strict mypy: 마지막 실행 PASS.
- 초기 Ruff 실패 반복과 mypy 실패를 보존합니다. 검사 합계의 정확한 elapsed는 durable 요약에 없어 완전한 시간 계측 증명을 주장하지 않습니다.
- 전체 acceptance는 FAIL이므로 completion의 `tests_passed=false`, `review_passed=false`입니다.
- main 구현 병합·통합 검사는 중단 조건 때문에 실행하지 않았으며 `integrated_commit=null`입니다.
- 전체 suite는 새 simulation/replay 금지 때문에 실행하지 않았습니다. 프런트엔드 변경·검사 및 웹 성과 공개는 해당 없습니다.
- 최초 explore는 plaintext/opaque mode 차이로 post 감사에 실패했습니다. plan이 원본 관측과 SHA를 재검증했습니다. 이후 plan/code/review의 opaque-mode 감사는 모델·non-message 인자·receipt 검증만 의미하며 메시지 원문 무결성을 주장하지 않습니다. 상세 제한은 `routing-limitations.md`에 보존합니다.

## 안전·보존·재개

CPU만 사용했습니다. 새 simulation/replay·GPU·네트워크 수집·PAPER/live 활성화·주문·운영 원장/DB·서비스·설정·원격 push는 수행하지 않았습니다. 다른 격리 작업과 루트 `HANDOFF.md`를 보존했습니다.

증거와 SHA는 audit `manifest.json`, handoff는 audit `HANDOFF.md`에 보존합니다. 구현은 미병합이고 검토 실패 상태이므로 worktree와 branch를 삭제하지 않습니다. main의 이 감독 기록과 worktree의 구현자 기록은 상태가 다르며, 재개 시 감독 기록과 실제 Git 상태를 우선하고 문서 충돌을 조정해야 합니다.

다음 시도는 명시적인 재개 승인과 새 검증 한도 아래 기존 소유 worktree를 재사용해야 합니다. 먼저 `final-review.md`, `worker-audit.md`, `verification-history.json`을 읽고 P1 결함과 fixture 계획을 교정합니다. 이번 시도에서 R2-01 전체 체크는 미완료로 유지합니다.

## 2026-09-16 복구 기록

- 상태: 복구 구현 완료, 독립 검토 대기 (R2-01 경제 평가는 계속 차단)
- 기준/통합: `d7ee8ca` / 없음
- 범위: 기존 네 대상 파일만 수정했습니다. 전략, collector, shared model,
  registry, runner, DB, 서비스와 주문 계층은 읽기 전용으로 보존했습니다.

## 복구 변경과 결정

- 명시적 거래 입력은 side·currency·유한 수치·양수 수량/가격·비음수 비용과
  ISO `YYYY-MM-DD` 체결일을 검증하고, KRW/USD 혼합과 시장 통화 불일치를
  거부합니다. 중복 식별에는 fee·tax·currency를 포함합니다.
- 모든 공개 계산은 호출자 Decimal context와 독립적인 precision 50,
  `ROUND_HALF_EVEN` context에서 실행합니다. 순손익은 realized/unrealized/
  dividend 등 실제 의존 항목이 모두 available일 때만 available입니다.
- 매수 tax를 포함한 체결 비용과 완전한 배당 evidence가 있는 배당 현금흐름을
  계산 현금에 반영합니다. 배당 evidence가 없거나 불완전한 현금은
  `unavailable`로 유지하고 진단값과 관측 `cash_krw`를 구분합니다.
- 저장 결과의 equity 날짜 중복·역순과 fill session 누락을 거부합니다. 별도
  주문 상태/timestamp를 체결로 추정하지 않으며 독립 달력 근거 없이 날짜 간격을
  결측으로 판정하지 않습니다.
- 직렬화된 component에 `currency`와 `unit`을 추가했습니다. 명시적 거래 금액은
  증명된 native 통화, 저장 결과의 FX/cash는 각각 KRW로 표시하며, 빈 입력의
  통화는 `null`로 남깁니다. FX 분해에는 native 통화·local KRW·`KRW_per_USD`
  rate unit을 보존합니다. CLI의 미지원 주문/timestamp metadata와 직렬화 계약도
  회귀 테스트에 고정했습니다.

## 복구 검증

- `backend/.venv/bin/python -m pytest tests/test_market_loss_accounting.py -q` —
  PASS, 21 tests, including rejection of order status and timestamp metadata.
- `backend/.venv/bin/python -m ruff check jusik/market_loss_accounting.py
  tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/python -m ruff format --check
  jusik/market_loss_accounting.py tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/python -m mypy --strict jusik/market_loss_accounting.py
  tests/test_market_loss_accounting.py` — PASS, 2 source files.
- 원본 manifest의 source SHA가 일치함을 확인했습니다. 기존 구현 결과는
  pre-unit-fix evidence로 보존하고, 구조화 단위 수정 후 승인된 추가 1회 진단을
  별도 결과로 실행했습니다. 최신 결과는 252 sessions·106 trades이며
  `blocked`이고, 완전한 realized/unrealized/dividend evidence가 없어 경제
  평가는 `not-evaluated`로 유지됩니다. 두 결과 JSON과 명령별 원문
  wall/CPU 기록은 저장소 밖 audit에 보관합니다.

- 이전 구현의 실패·fixture 초과 기록은 삭제하거나 재작성하지 않고 앞부분의
  감독 기록과 원래 audit에 보존합니다.


## 감독 통합 검증

- 현재 기술 상태: 복구 완료. 독립 Terra 최종 검토 `93a6211`에서 중요 지적 없음. 통합 전 `daf7ba5`, 통합 `20ee636`.
- main focused pytest21·Ruff check/format·configured strict mypy2파일·diff check PASS. 검토한 제품/테스트/계약 소스와 main의 일치를 확인했습니다.
- 최초 검토에서 structured currency/unit 누락과 CLI metadata 회귀, 실행 소스 연결 부족을 찾아 수정했습니다. 최종 `worker/final-source-manifest.json`은 커밋·module/test·pilot 입력/출력 SHA와 실행 전후 소스 불변을 연결합니다.
- 저장pilot 진단은 복구 중 총3회입니다. 최초 출력, 통화 보완 후 출력, 최종 소스 고정 출력은 모두 보존하며 추가2회는 각각 실제 검토 지적의 검증을 위해 감독이 승인했습니다. 새 engine/replay/수집은 실행하지 않았고 main에서는 소스 일치로 증거를 재사용했습니다.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20260916-loss-recovery/integration.json`, `integrated/`, `source/`. 소스·패치·SHA 보관 후 병합된 worktree와 branch를 정상 제거했습니다.
- 원래 runner blocked 기록과 실제 자료 부족은 유지합니다. R2-01 전체 체크·성과 수치·전략·웹·PAPER/live·운영DB·원격push는 바꾸지 않았습니다.
