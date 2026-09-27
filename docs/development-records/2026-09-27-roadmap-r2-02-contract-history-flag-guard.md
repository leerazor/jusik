# 새 PAPER manifest의 outer historical contract 차단

- 상태: 완료 (scope 승인, 구현, 별도 review, local main 통합); 투자 상태 `NOT_EVALUATED`
- 기록 시각: 2026-09-27T11:14:33Z
- 작업 slug: `roadmap-r2-02-contract-history-flag-guard-v1`
- 기준/통합: `19432bdbdba87d86d195e564697d40121ec5b29d` / `7411e7518407a69a053ce438f3d9e98cfc2d244b`
- 범위: outer `PaperCostContract.applies_to_frozen_history=True`인 상태에서 `manifest()`가 새 PAPER manifest를 출력하는 경로를 거부합니다. 요율·historical pilot·법정 적용성·경제 평가·mandate는 바꾸지 않았습니다.

## 변경과 결정

- 직전 source/test slice가 `BrokerCostProfile.applies_to_frozen_history=True`를 막았지만, outer contract flag는 여전히 validator가 거부할 manifest를 만들 수 있었습니다.
- 독립 roadmap scope reviewer는 두 플래그가 서로 다른 state field의 같은 serialization boundary를 보호하는 별도 경우임을 확인하고, 고정 BanKIS fixture를 쓰는 source/test 두 파일만 승인했습니다.
- `PaperCostContract.manifest()`는 outer contract flag가 true이거나 포함된 profile 중 하나가 true이면 고정 오류 `paper_cost_contract_frozen_history_forbidden`를 냅니다. 기존 정상 false manifest와 inner-profile 거부는 그대로 유지합니다.
- provisional technical assumption: historical용 outer contract는 새 PAPER manifest의 허용 입력이 아닙니다. 이는 기존 serializer/validator 계약을 맞추는 임시 개발 전제이며 최종 데이터 허용 조건이나 투자 승인 기준으로 동결하지 않습니다.

## 문서·계약 영향

- `docs/market-cost-diagnostics.md`가 outer contract와 embedded profile 둘 다의 historical flag를 manifest 생성 시 거부한다고 기록합니다.
- UI/API·설정·요율·mandate·투자 기준·roadmap checkbox·preregistration은 바뀌지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_broker_cost_profiles.py` — 35 passed.
- `backend/.venv/bin/ruff check backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 두 파일 format 상태.
- `backend/.venv/bin/mypy --strict backend/jusik/broker_cost_profiles.py backend/tests/test_broker_cost_profiles.py` — 두 파일 오류 없음.
- `git diff --check 19432bd..7411e75` — 통과.
- 별도 reviewer PASS attempt `545a0c57856d4a9b8e55281ff8293f19`; implementation attempt `e1009e2dccbc44008fc6b041ee269491`, baseline/main commit과 두 파일 SHA에 결속됨: source `b3072e8da7d82f940e2c7177aff59e198d5b38c8cfdf068839f8279111c2c231`, test `2970342ba00968d2f89eb29cabff892fe3d8288954bd2373f33a9cc327126f35`.
- 전체 backend suite와 금융자료 기반 평가는 실행하지 않았습니다. 오프라인 serialization invariant만 확인했습니다.

## 안전·운영 상태

- 금융자료/provider/API, credential, 유료 구매, 운영 DB, PAPER/live 실행, 실주문과 remote push는 없었습니다. documented runner command와 기존 timer를 사용했으며 service 설정을 바꾸지 않았습니다.
- runner task는 `ENGINEERING_COMPLETE/NOT_EVALUATED`로 닫혔습니다. R2-02의 전체 법정 적용성과 경제 평가는 자료와 receipt 부족으로 수행하지 않았습니다.
- held-band draft `docs/research/portfolio-held-band-preregistration-draft-v2.json`은 `registered=false`, `approved=false`, `execution_allowed=false`, unresolved null 23개 그대로 유지됩니다. held-band FINAL_VALIDATION/OOS는 승인된 preregistration과 적격 미래 자료까지 task-local BLOCKED/PENDING이며, 외부 readiness identity binding도 검증된 producer/validator 계약까지 PENDING입니다.

## 증거와 재개

- planner `planner-c625027ffd943ea60332ad9b`, planning attempt `914f0db4bcbf48979f872abaaf519137`, scope review attempt `427ea2b9edea4039af18374c8b9d6008`은 독립 approval을 남겼습니다. completion review receipt는 attempt `545a0c57856d4a9b8e55281ff8293f19`로 보존됩니다.
- task-local blocker는 없습니다. 다음 동작은 문서 반영 후 roadmap queue를 재개하고 이 main code change를 반영한 bounded discovery를 확인하는 것입니다. generic research queue는 원래 paused로 둡니다.
