# 새 PAPER manifest의 historical profile 차단

- 상태: 완료 (scope 승인, 구현, 별도 review, local main 통합); 투자 상태 `NOT_EVALUATED`
- 기록 시각: 2026-09-27T11:01:48Z
- 작업 slug: `roadmap-r2-02-profile-history-flag-guard-v1`
- 기준/통합: `5182304d1cf88993ae4628c73efdc773a0e819ca` / `3877e8bf933a0314b2d45ca81024fc6d1626b6f4`
- 범위: 새 `PaperCostContract` manifest가 frozen-history용 profile을 포함하면 고정 오류로 거부합니다. 요율·historical pilot·법정 적용성·경제 평가·mandate는 바꾸지 않았습니다.

## 변경과 결정

- latest-main planner가 offline reproduction을 제안했고 독립 roadmap scope reviewer가 `broker_cost_profiles.py`와 test 한 쌍에 한정해 승인했습니다.
- `PaperCostContract.manifest()`는 포함 profile의 `applies_to_frozen_history` flag를 검사합니다. true면 `ValueError("paper_cost_contract_frozen_history_forbidden")`를 내며 manifest를 생성하지 않습니다.
- regression은 기존 정상 BanKIS profile에서 한 profile만 historical flag로 바꾼 unsafe contract의 거부를 확인합니다. 기존 정상 profile·부분집합·round-trip 검증은 함께 유지됩니다.
- provisional technical assumption: historical용으로 표시된 profile은 새 PAPER manifest의 profile 집합에 속하면 안 됩니다. 이는 serializer 경계에 대한 개발용 가정이며, 승인 전 최종 데이터 허용 기준이나 투자 승인 조건으로 동결하지 않습니다.

## 문서·계약 영향

- `docs/market-cost-diagnostics.md`에 manifest 경계의 거부 규칙과 한계를 기록했습니다. 기존 historical modeled rate의 비소급 원칙을 구현에서 fail-closed로 집행합니다.
- 사용자 UI/API, 설정, 요율, mandate, 투자 기준, roadmap checkbox 및 preregistration은 바뀌지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_broker_cost_profiles.py` — 34 passed.
- `backend/.venv/bin/ruff check backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 두 파일 format 상태.
- `backend/.venv/bin/mypy --strict backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 두 파일 오류 없음.
- `git diff --check 5182304d1cf88993ae4628c73efdc773a0e819ca..3877e8bf933a0314b2d45ca81024fc6d1626b6f4` — 통과.
- 별도 reviewer PASS attempt `e8e648cda44348329d17c5056bb84229`; implementation attempt `40507c5175ab4cadadc77463b807f29e`, baseline/main commit과 다음 두 파일 SHA에 결속됨: source `17a1ff9eb8e851602938f807bd54324f4bd9b05280911d2f4d4e78ea317f287f`, test `2fc6834567b784346a0b0ae6306d5900e7c1349dd7ee60da9cb4193bec1c8301`.
- 전체 backend suite와 금융자료 기반 평가는 실행하지 않았습니다. 이 수정은 오프라인 code contract에 한정되며 비용·자료 없이 완료를 증명할 수 있는 유효성만 확인했습니다.

## 안전·운영 상태

- 외부 금융자료/provider/API, credential, 유료 구매, 운영 DB, PAPER/live 실행, 실주문과 remote push는 없었습니다. roadmap queue는 documented `run-once`로 discovery를 진행하고 기존 timer가 implementation/review cycle을 수행했습니다. service 설정은 바꾸지 않았습니다.
- runner task는 별도 `ENGINEERING_COMPLETE/NOT_EVALUATED`로 닫혔습니다. R2-02 전체 비용 법정 적용성·경제 평가는 receipt와 법정 범위 자료가 아직 부족합니다.
- held-band draft `docs/research/portfolio-held-band-preregistration-draft-v2.json`은 재확인 시 `registered=false`, `approved=false`, `execution_allowed=false`, 23 unresolved nulls 그대로입니다. held-band FINAL_VALIDATION/OOS는 승인된 preregistration과 적격 미래 자료까지 task-local BLOCKED/PENDING입니다. 외부 readiness identity binding도 producer/validator 계약 부재로 PENDING입니다.

## 증거와 재개

- scope approval: planner `planner-94383a306528f2d8cd9d7036`, scope attempt `6f69eae7f5ad4921abd8b1783d13fedf`. completion review receipt와 attempt 증거는 `/home/kwl/.local/share/jusik/roadmap-development-runner/runner.db` 및 `/home/kwl/.local/share/jusik/roadmap-development-runner/attempts/40507c5175ab4cadadc77463b807f29e`에 보존됩니다.
- 작업 구현에는 차단이 없습니다. 다음 동작은 문서 반영 후 roadmap queue를 재개하고 최신 backend fingerprint의 기존 bounded planner/discovery를 확인하는 것입니다. 기존 generic research queue는 paused 상태를 유지합니다.
