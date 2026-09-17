# R1-04 회계 계약 첫 slice 개발 이력

- 현재 상태: 첫 기술 slice 완료. 재시도 `33c9cb940ee7486cb40ba692842dc732`의 구현·독립 검토·local main 검증·증거 보존·정리를 완료했습니다. 전체 R1-04는 미완료입니다.
- 아래 기존 기록은 이전 시도 `bf7be9ff5dd64096848f7599f0c8265f`의 차단 이력입니다. 소급 승인하거나 삭제하지 않습니다.
- 작업: `roadmap-r1-04-v1`; attempt `bf7be9ff5dd64096848f7599f0c8265f`.
- 기준: `5688c38b1f8c091db5e52d495df5262f5d1ed749`; 등록 커밋 `e84aa55`. 구현 main 통합 없음.
- 소유 worktree: `/home/kwl/projects/jusik-r1-actions-bf7b`, branch `feat/r1-actions-bf7b`. 미커밋 구현을 보존합니다.

## 범위와 변경

R0 완료를 확인한 뒤, 공통 history 모델·직렬화·snapshot hash를 바꾸지 않는 별도 연구용 split/dividend 입력 adapter와 순수 Decimal 회계 변환을 계획했습니다. Luna가 새 module, 테스트, fixture, 계약 문서와 개발 기록 초안을 작성했습니다. 이 구현과 계약 문서 초안은 main에 병합하지 않았습니다. collector·universe·사건 cutoff·전략·PAPER 계약은 변경하지 않았습니다. 실제 approximate source의 빈 actions·incomplete 상태도 그대로입니다.

## 차단 근거

- 작업 지시는 신규 회계 테스트와 기존 순수 회귀 두 개만 허용했습니다. Luna는 기존 `test_market_history_approximate.py`, `test_research_dividend_overlay.py` 파일 전체를 두 번 실행했습니다. 첫 실행 40개, 신규 회계 테스트를 포함한 마지막 실행 60개가 통과했습니다. 이 통과는 acceptance 통과가 아닙니다.
- 기존 approximate 테스트에는 합성 `stage="pilot"` 요청과 `run_approximate_market_research` 실행이 있습니다. 실제 자료 pilot 실행은 확인되지 않았지만, 이번 계획의 engine/pilot 0회 경계를 충족하지 못했습니다.
- 최초 신규 테스트 실행 후 입력 시나리오가 바뀌었습니다. 독립 Terra 감사에서 실행된 신규 fixture의 보수적 하한21개를 확인했습니다. 최종 목록19개는 시도 전체의 합집합이 아니며 상한20개를 초과했습니다. 결과는 외부 audit에 저장했습니다.
- code 역할의 첫 public receipt가 준비한 routing receipt와 일치하지 않아 사후 delivery 검증에 실패했습니다. 모델 불일치로 확대 해석하지 않습니다.
- 추가 계산·구현 병합·main 통합 검사를 중단했습니다. 범위·실행 이력과 receipt 불일치를 허용된 자동 복구 label로 바꾸지 않습니다.

## 검증과 제한

마지막 worker pytest60, Ruff check/format, configured strict mypy 통과 보고와 실제 pytest 결과를 보존했습니다. 그 이전 실패와 입력 변경도 보존했습니다. `tests_passed=false`, `review_passed=false`로 완료 응답을 제출합니다. main 통합 검사는 미실행입니다. 독립 검토는 추가 테스트 없이 실행 경계와 증거를 읽기 전용으로 확인합니다.

경제 평가는 `not-evaluated`입니다. 실제 행사 자료 연결, benchmark·미래 관찰 및 전체 R1-04 acceptance는 없습니다. 로드맵 체크박스는 미체크를 유지합니다. 성과 비교가 없어 웹 성과 catalog를 변경하지 않았습니다.

## 안전·운영 상태와 재개

실주문·PAPER/live 활성화·운영 DB/원장·서비스·설정·remote push·GPU 변경은 없습니다. 다른 격리 작업과 기존 handoff를 보존했습니다. 이번 worktree는 미병합·미커밋이므로 제거하지 않았습니다.

증거와 source snapshot은 `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-04-bf7be9ff/`에 있습니다. `observed-pytest-invocations.json`, `observed-pytest-results.json`, `code-routing-failure.json`, 독립 `review.md`, `evidence-manifest.json`, `HANDOFF.md`를 확인합니다. 다음 명시적 재시도는 같은 branch/worktree를 재사용하고, 변경 입력까지 포함한 전체 fixture 목록과 검사 명령을 실행 전에 고정해야 합니다. 이전 실패 기록을 삭제하거나 성공으로 재해석하지 않습니다.


## 명시적 재시도 완료 (2026-09-17)

- Task `roadmap-r1-04-v1`, attempt `33c9cb940ee7486cb40ba692842dc732`.
- 요청 기준 `5688c38b1f8c091db5e52d495df5262f5d1ed749`, 시작 main `d813f6e`, 재등록 `bf727f1`. 기존 소유 worktree와 branch를 재사용했습니다. 구현 `e3fa76a`, review 보완 `5405f3792a0bbd3662fb8d10a9e50cfc09943b0a`, main 통합 `c39242ec208d5bac9cdb3d3f2aa0076417e2af74`.
- 공통 history 모델·직렬화·snapshot hash는 그대로 두고 `backend/jusik/market_history_action_accounting.py`에 별도 legacy split adapter와 명시적 split/dividend 입력·순수 Decimal 회계 전이를 추가했습니다. raw basis·timezone-aware 유효/지급 경계·명시적 배당 권리를 요구합니다. 조정가격·불명확한 기준은 unsupported, 빠진 권리·가격은 insufficient로 남기며 원상태를 보존합니다.
- split은 분수 수량과 단가를 변환하고 대상 자산 가치·총원가 및 전체 NAV를 보존합니다. 배당 발생 시 권리를 고정하고 지급 시 같은 의미의 미수금을 현금으로 옮깁니다. ID/hash 재실행·충돌, 지급 사실 변조, strict bool과 상태 등급 검증을 제공합니다. 반올림·inexact 계산은 묵시적으로 적용하지 않습니다.
- 사용자 계약 문서는 `docs/market-research.md`를 갱신했습니다. collector·universe·사건 cutoff·전략·PAPER 및 공유 모델은 변경하지 않았습니다. 실제 actions는 빈 상태·incomplete, 경제 상태는 not-evaluated입니다.

### 재시도 검증과 독립 검토

`backend/`의 각 소유 `.venv`에서 Python3.13.15를1회 확인한 후 아래 검사를 수행했습니다. 감사 경로의 `validate.py`와 `checks.json`에 정확한 명령·cwd·종료 코드·시간·로그 경로가 있습니다.

- `python -m pytest -q -p no:cacheprovider tests/test_market_history_action_accounting.py 'tests/test_market_history_approximate.py::test_approximate_readiness_reports_prepared_file_and_market_fx[KR]' tests/test_research_dividend_overlay.py::test_native_ledger_preserves_long_decimal_through_payment` — 최종 worker와 통합 main 각각31개 통과. 기존 두 node는 오프라인 readiness와 순수 Decimal 계산만 실행합니다.
- `python -m ruff check jusik/market_history_action_accounting.py tests/test_market_history_action_accounting.py` 및 `python -m ruff format --check` 동일 두 파일 — 통과.
- `python -m mypy --config-file pyproject.toml jusik/market_history_action_accounting.py tests/test_market_history_action_accounting.py` — strict 검사 통과.
- `git diff --check` — 통과. frontend 변경이 없어 frontend build는 실행하지 않았습니다. 전체 engine/pilot/final·네트워크 수집·최적화·GPU·PAPER 연구도 실행하지 않았습니다.
- Terra가 초기 상태 등급 검증 누락을 지적했고, 같은 Luna가 수정했습니다. 최종 `5405f37`의 독립 재검토는 PASS입니다. explore/plan/code/review 역할의 model-only receipt·parent/child·model 사후 감사도 PASS입니다. opaque host의 raw 전달문 무결성을 검증했다고 주장하지 않습니다.
- 이번 검사는 기존19개 fixture를 재사용하고 신규·변형13개를 기록했습니다. 신규 상한20개, 각각 최대4심볼/40세션, seed0, 단일 CPU 프로세스, 관련 검사 합계12.180초/900초를 지켰습니다. agent 자체의 테스트 호출 횟수 제한은 현재 tracked delivery 정책으로 대체했으며 과거 위반은 그대로입니다.
- 이번 초기 pytest는 timestamp 입력 오류와 임시 경로 상위 폴더 누락으로 실패했고, Ruff import/line length·format 실패도 보존했습니다. 소유 Python 환경 확인은 성공했으며 임시 경로 문제는 검사 호출 준비 문제였습니다. 반복 worker1 로그가 덮어써진 한계를 기록하고, 초기 pytest/Ruff 출력은 원래 child tool-result에서 복원했습니다. 경고2개는 기존 의존성 deprecation이며 결과를 실패로 숨기지 않았습니다.

### 증거·handoff·정리

- Durable audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-04-33c9/`. `evidence-manifest.json`에 SHA-256이 있으며, PLAN·입력 inventory·source·최종 patch·환경·checks·review·routing·integration-proof·cleanup·HANDOFF를 보관했습니다. worktree 제거 전에 필요한 증거와 해시·handoff를 검증했습니다.
- 기존 stale untracked 개발 기록 초안도 `before/`에 보존했습니다. 통합 검사 후 `/home/kwl/projects/jusik-r1-actions-bf7b`와 `feat/r1-actions-bf7b`만 force 없이 정상 제거했습니다. 다른 격리 작업은 재개하거나 삭제하지 않았습니다.
- 루트 `HANDOFF.md`와 audit의 `HANDOFF.md`에 현재 상태·다음 시작점을 저장했습니다. 성과 비교가 없어 웹 성과 catalog는 변경하지 않았습니다. 기술 작업 상태 공개는 runner가 담당합니다.
- 실제 자료 연결·자료 완전성·전체 R1-04 acceptance는 후속 작업입니다. 전체 checkbox는 미체크이며 benchmark·미래 관찰 없이 경제적 성공이나 approximate 승격을 주장하지 않습니다. PAPER/live 활성화·주문·운영 DB/원장·서비스·설정·remote push 변경은 없습니다.
