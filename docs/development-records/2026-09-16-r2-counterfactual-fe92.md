# R2-06 기술 구현 통합 — 개발 완료 복구

- 상태: 기술 모듈·CLI 완료. local main 통합 `5ec8f2f` 및 통합 검증 완료.
- 기록 시각: 2026-09-17T00:23:03.114594+00:00.
- 작업 slug: `r2-counterfactual-fe92`; 구현 `8fc46d44df56e3db3b6165fe349080b91d924b70`.
- 사용자 자율 개발 요청에 따른 감독 결정으로 새 검증에서는 agent 자체 단위 테스트 fixture 개수 상한을 종료 조건으로 쓰지 않습니다. 아래 과거 실패 기록은 소급 변경하지 않습니다. 사용자 명시 한도와 실제 금융 연구 조건은 유지합니다.
- 이미 준비된 회계 결과의 비용·배당·환율 단일 가정 비교 모듈과 CLI를 통합합니다. 하나의 기존 leaf 값만 변경할 수 있으며, 자료 부족을 0으로 만들거나 기여를 합산하지 않습니다.
- 새 검토에서 입력 hardlink 별칭 덮어쓰기와 없는 경로/null 혼동을 수정했습니다. 입력 원본·SHA와 unavailable 상태를 보존합니다.
- worker: 비교/손실 회계 focused pytest52, Ruff check/format, configured strict mypy, diff check PASS. 독립 Terra review의 P1/P2 해소 후 최종 material finding 없음.
- 합성 CLI smoke exit0, 배당/FX unavailable 보존, economic_evaluation=not-evaluated. 실제 시장 결과나 수익 개선 검증으로 해석하지 않습니다.
- 문서·계약: `docs/research/market-counterfactual-comparison.md` 갱신. 기존 회계/전략/투자 정책/API/UI 변경 없음. 실제 provider·engine·PAPER/live·운영DB·원격push 실행 없음.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-delivery-recovery`; `r2-worker/smoke-02/manifest.json`, 검사 로그, `r2-source/`가 새 소스·증거입니다. main pytest52개·Ruff/format·strict mypy PASS, CLI 결과 동일·input SHA 보존을 확인했습니다. 소스/환경/증거 보관 후 전용 worktree/branch를 정상 제거했습니다.
- 전체 R2-06 실제 자료 acceptance와 수익률 평가는 계속 미완료입니다. 기술 모듈 완료와 구분하며 기존 runner blocked 시도를 성공으로 바꾸지 않습니다.

## 과거 시도 기록 보존

# R2-06 제한 재시도 — fixture 상한 중단

- 현재 상태: 차단. task `roadmap-r2-06-v1`, attempt `16e000f1b0cb4314b54eb2a5acbe50f0`, 이전 attempt `474fb22d193c4302893e77e27f8d1b55`.
- 소유 worktree `/home/kwl/projects/jusik-r2-counterfactual-fe92`, branch `feat/r2-counterfactual-fe92`를 재사용했습니다. 구현 `f4070f24b11c8d9ec3817e833a3ef8991ae8d119`는 미병합이며 보존합니다.
- 요청 기준 d0d029996ea993216036385962c9153968ea61fe가 main 조상임을 확인했고 원래 입력 4개 SHA, 이전 증거48개 SHA, R0 완료와 현재 mandate를 다시 확인했습니다. worktree/main Python3.13.15를 각각 검사 전 한 번 확인했습니다.

## 변경과 검증

Luna가 기존 네 파일 범위에서 container/scalar 및 mapping/list 교체를 거절하고, 실제 단일 leaf에서 canonical 경로와 전후 값을 기록하도록 수정했습니다. 최상위 scalar와 이전 fees/taxes→null 재현, 역방향·빈·중첩 container 경계를 보완했습니다. 한국어 계약 예시도 기준 가정에 맞췄습니다. 기존 회계 엔진은 수정하지 않았습니다.

fresh focused pytest45개(비교24, 기존 회계21), Ruff check/format, configured strict mypy와 diff check는 통과했습니다. 초기 format 실패는 한 번 수정 후 통과했습니다. Terra는 이전 코드 결함 해소를 확인했고 감독의 cap 판정 전달 전에 기존 경계 테스트2개를 실행해 통과했습니다. 그러나 아래 상한 초과로 독립 review gate는 차단이며, 모든 통과 로그를 완료 판정으로 사용하지 않습니다. main 구현 병합·통합 검사는 실행하지 않았습니다.

## 중단 근거

기존 마지막 worker pytest 산출물에서 준비 wrapper49개, canonical JSON 기준 서로 다른 완전한 wrapper 최소25개를 읽기 전용으로 확인했습니다. fixture 최대24 조건을 초과했습니다. 파일 역할3개, report payload12개 또는 report 조합8개라는 수로 입력 metadata·assumptions 변형을 제외해 상한 준수를 주장하지 않습니다. 덮어쓴 중간 변형은 이 하한에 포함되지 않습니다. cap 확인 후 추가 검증·수정·병합·정리를 중단했습니다. 이 상한 중단은 자동 복구 label에 해당하지 않아 recovery_kind를 지정하지 않습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r2-06-16e000f1`.
- `fixture-cap-evidence.json`과 `fixture-snapshot/`은25개 이상 입력과 원본 SHA의 근거입니다. `fixture-bounds-correction.md`는 기존 역할 수 집계의 한계를 정정합니다.
- `review.md`, `logs/`, source snapshot, patch, `evidence-manifest.json`, `HANDOFF.md`를 worktree 밖에 보존합니다. 삭제는 수행하지 않았습니다.
- model-only routing은 child receipt·모델·nonmessage 인자를 검증했습니다. 최초 explore/plan plaintext 모드와 실제 opaque transport 차이는 원본 manifest를 보존한 별도 감사로 기록했으며 원문 무결성을 주장하지 않습니다.
- 다음 명시적 재개는 같은 소유 branch를 재사용하고, 검사 전에 입력 fixture 목록·전체 수와 검증 한도를 고정해야 합니다. 반복 파일 역할 수나 테스트 수만으로 상한을 입증하지 않습니다.
- 기술 slice와 전체 R2-06은 미완료입니다. 실제 준비 자료·benchmark·미래 관찰 acceptance는 blocked, 경제 평가는 not-evaluated이며 체크박스는 변경하지 않았습니다.
- network/provider/historical engine/replay/GPU 실행0회. PAPER/live·주문·운영 DB·원장·서비스·설정·remote 변경없음. 새 성과 비교가 없어 웹 catalog는 변경하지 않았습니다.

## 이전 시도의 역사 기록

# R2-06 오프라인 counterfactual 비교 — 재검토 중단

- 현재 상태: 차단. 동일한 단일 가정 검증 결함이 독립 review에서 두 번째 확인되어 사용자 중단 조건을 적용했습니다.
- task/attempt: `roadmap-r2-06-v1` / `474fb22d193c4302893e77e27f8d1b55`; 이전 attempt: `fe9204931f0b446f8dfba0d21473f39d`.
- 요청 기준: `d0d029996ea993216036385962c9153968ea61fe`는 현재 main의 조상이며 첨부 4개 SHA와 최신 mandate가 일치했습니다.
- 구현: 기존 소유 worktree `/home/kwl/projects/jusik-r2-counterfactual-fe92`, branch `feat/r2-counterfactual-fe92`, 최종 커밋 `0bab5ad04ff03f4c9561a522e202586bc04e4ccc`. 구현 main 통합은 없습니다.

## 이번 재시도의 변경과 검증

Luna가 별도 prepared-report 비교 모듈·CLI, 관련 테스트와 한국어 계약을 구현했습니다. 원본 bytes SHA와 공통 계약을 대조하고 동일 통화·단위의 available 값만 Decimal 차감합니다. 원본 report와 unavailable/diagnostic을 보존하고 배당·FX 근거 부족은 blocked delta와 재개 입력으로 남깁니다. 초기 계좌 통화와 결과 통화를 분리하고 시나리오별 변경 경로·전후 값을 기록합니다. 구현은 아직 독립 review를 통과하지 않았으므로 사용 완료 계약으로 간주하지 않습니다.

기존 전용 venv Python 3.13.15를 확인했고 fresh focused pytest 43개(새 비교22개와 기존 손실 회계21개), Ruff check/format, configured strict mypy 2파일은 통과했습니다. 초기 독립 review 후 동일 Luna가 수정하고 fresh 검사를 다시 통과했으나 재검토에서 단일 가정 결함이 남았습니다. main 통합 검사는 review gate 미통과로 실행하지 않았습니다.

## 중단 근거와 재개 조건

`market_counterfactual_comparison.py`에서 cost 객체 `{fees: "1", taxes: "1"}`를 `null`로 교체하면 하위 두 가정 제거를 한 atomic 변경으로 처리합니다. `change.path="cost"`를 선언한 envelope가 통과하는 것을 Terra가 재현했습니다. 최초 단일 가정 위반 지적의 두 번째 발생이므로 이번 시도에서 추가 수정·검사·병합은 중단했습니다. 다음 허용된 재시도는 container 교체를 거절하거나 하위 leaf 변경을 모두 계산하고 이 경계를 포함한 fresh tests 및 독립 review를 다시 수행해야 합니다. 자동 복구 분류는 `implementation` / `actionable_review`입니다.

- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r2-06-474fb22d/`; `review-initial.md`, `review-final.md`, `stop-evidence.json`, final2 검사 로그, 소스 snapshot/patch와 `evidence-manifest.json`을 보존합니다.
- handoff: 같은 audit의 `HANDOFF.md`. 미병합 소유 worktree/branch를 보존하며 다른 worktree와 기존 루트 HANDOFF는 변경하지 않았습니다.
- 전체 R2-06: 미체크. 실제 준비 결과·benchmark·미래 관찰 acceptance가 없으며 경제 평가는 not-evaluated입니다. 기술 slice도 review 미통과로 미완료입니다.
- network/provider 수집·historical engine/replay·GPU 실행0회. PAPER/live·주문·운영 원장/DB·서비스·설정·remote 변경0회. UI·연구 성과 공개는 해당 없습니다.

## 이전 시도 이력

### 이전 환경 준비 중단

- 상태: 차단. 기술 slice 및 전체 R2-06 모두 미완료입니다.
- task/attempt: `roadmap-r2-06-v1` / `fe9204931f0b446f8dfba0d21473f39d`
- 기준: `d0d029996ea993216036385962c9153968ea61fe`; 등록 커밋 `bfa2590`. 구현 통합 커밋은 없습니다.
- 소유 worktree/branch: `/home/kwl/projects/jusik-r2-counterfactual-fe92`, `feat/r2-counterfactual-fe92`.

## 확인과 결정

기준 main, 첨부 evidence 네 개 SHA, R0 완료와 최신 mandate를 확인했습니다. Luna 읽기 전용 조사와 Astra 계획 검토를 진행했습니다. 준비된 결과만 읽는 별도 비교 모듈과 CLI를 계획했으며 기존 loss accounting availability를 보존하고 배당·FX 근거 부재를 0으로 대체하지 않습니다. 기준 대비 차이는 시나리오별로 기록하고 비가산적인 기여를 합산하지 않습니다.

## 중단 근거

감독이 한 shell에 순차 배치한 `uv venv`와 `uv pip install --offline`이 모두 `/home/kwl/.cache/uv`의 읽기 전용 파일시스템에서 잠금용 임시 파일 생성에 실패했습니다. 첫 실패 후 다음 명령이 실행되도록 배치한 것이 같은 실패 2회에 도달한 원인입니다. 두 번째 실패 직후 사용자 중단 조건을 적용했습니다. 환경 우회나 추가 설치, 구현, 테스트를 진행하지 않았습니다.

제품 코드·테스트·한국어 기능 계약은 아직 작성하지 않았습니다. focused pytest, Ruff, configured typecheck, 독립 review, main 구현 통합 검사는 미실행입니다. 통과로 보고하지 않습니다. 기존 authoritative 체크박스는 변경하지 않았습니다. 실제 비교 자료, benchmark와 미래 관찰 자료도 확보하지 않았고 경제 평가는 not-evaluated입니다.

## 보존과 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-06-fe920493`; `stop-evidence.json`은 두 실패 명령, `input-verification.json`은 원본 hash 일치, `PLAN.md`는 제한 계획을 보존합니다. `HANDOFF.md`와 `evidence-manifest.json`에서 다음 시작점과 SHA를 확인합니다.
- 최초 explore 호출은 plaintext 모드로 준비했으나 host가 opaque message를 기록하여 exact-message post 감사를 주장하지 않습니다. 제한은 `routing-limitations.md`에 보존하고, 후속 plan은 관측된 opaque 모드로 준비했고 post 감사가 PASS했습니다. nonmessage 인자·모델·receipt 검증만 의미하며 원문 메시지 무결성은 주장하지 않습니다.
- 차단된 소유 worktree/branch는 보존합니다. 기존 다른 여섯 worktree와 루트 HANDOFF는 변경하지 않았습니다.
- network/provider 수집·historical engine/replay·GPU 실행은 0회입니다. PAPER/live·주문·운영 원장/DB·서비스·설정·remote 변경은 없습니다. UI 변경과 연구 성과가 없어 웹 공개는 해당 없습니다.
- 명시적 재시도에서 동일 소유 branch/worktree를 재사용합니다. 먼저 작업 전용 쓰기 가능한 uv cache와 오프라인 의존성 준비 방법을 확인하고 새로운 검증 한도를 고정해야 합니다. 이 시도에서는 자동 재시도하지 않습니다.
