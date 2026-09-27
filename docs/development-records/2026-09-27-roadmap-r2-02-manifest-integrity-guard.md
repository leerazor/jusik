# PAPER cost manifest의 stale profile identity 검토 차단

- 상태: `WAITING_EXTERNAL` (implementation commit은 main에 통합됐으나 별도 완료 reviewer verdict FAIL; `ENGINEERING_COMPLETE` 아님)
- 기록 시각: 2026-09-27T11:36:17Z
- 작업 slug: `roadmap-r2-02-manifest-integrity-guard-v1`
- 기준/구현 통합: `7f13d3367a0a1d7c2705fd52b3c073945f4f6bd7` / `6c11427d4bd0bbea0e9704cc02b3040e0d6f5d58`
- 범위: 변경된 비용 profile의 기존 hash/ID가 새 PAPER manifest에 남는 경로를 막는 source/test 수정 후보입니다. 투자 상태나 비용 적용성을 판단하지 않았습니다.

## 후보 구현과 검토 상태

- planner `planner-813409e72dcfc0f79588dd4b` (attempt `69b4bbbc82604876a5f0cd59ce414d94`)가 `PaperCostContract.manifest()`가 내부 profile 변경, stale `profile_hash`, stale `contract_id`를 저장 validator가 거부하기 전에 출력할 수 있다고 제안했습니다. 독립 scope review attempt `410d11130ea549b7a0b5a1ef4d0de37b`가 offline BanKIS fixture와 기존 source/test 쌍으로 한정 가능한 작업을 승인했습니다.
- implementation attempt `51c4b14e4d9d4434a46cc356de1953d2`는 manifest 생성 중 canonical validator를 호출하고 profile identity 비교를 보강했습니다. runner completion artifact는 `tests_passed=true`를 기록합니다.
- 별도 host completion reviewer attempt `a17f257d0ae648d98e2320b638cdd670`은 verdict `FAIL`을 반환했습니다. 저장 receipt에는 `verdict`와 identity/hash만 있으며 finding이나 수리 이유는 없습니다. runner failure code는 `review_rejected`이며 상태를 `WAITING_EXTERNAL/independent_review_pending`으로 유지합니다.
- code commit `6c11427`은 runner의 documented integrate-before-review 경로에 따라 local main에 남아 있습니다. reviewer PASS가 없으므로 engineering complete, PAPER 승인, 원격 게시로 해석하지 않습니다. reviewer가 남긴 실행 가능한 수정 근거나 명시적 retry 조건이 없으므로 같은 후보를 자동 재시도하거나 verdict를 덮어쓰지 않습니다.
- provisional technical assumption: 변경된 rate/source/profile identity는 새 manifest에서 현재 hash·ID와 일치해야 합니다. 이는 serialization contract 조사용 임시 전제이고, 법정 요율·최종 자료 허용·투자 합격 기준을 정의하지 않습니다.

## 독립 READY 재탐색

- 실패 review가 다른 task를 막지 않도록 최신 main `6c11427`에서 기존 planner가 waiting을 반환한 뒤 bounded read-only engineering discovery가 실행됐습니다.
- discovery attempt/planner ID `b61e47a7c3c240f5b8298293d94c42a2`는 `no_work`를 반환했습니다. `paper_execution_contract`, `research_future_observation_replay`, `research_market_calendar`, `market_performance_metrics`, `research_portfolio_performance_metrics`, `market_history_action_accounting`, `market_loss_accounting` 7개 domain의 canonical source/test 쌍 14개를 bytes SHA-256으로 기록했습니다. 원 evidence는 `/home/kwl/.local/share/jusik/roadmap-development-runner/discovery/b61e47a7c3c240f5b8298293d94c42a2/result.json`에 보존됩니다.
- alternative review는 배당 replay 불일치가 기존 회귀로 처리됨, uncertain 주문/취소·중복 호출의 새 재현 없음, 확인되지 않은 날짜의 새 calendar 오류 근거 없음, `market_performance_metrics`는 고정 evaluator SHA policy를 바꾸지 않고 수정 불가라고 기록했습니다.
- 재개 조건은 현재 기준 HEAD에서 잘못된 동작을 보이는 최소 offline 입력과 기대 결과를 확보하는 것입니다. 구체적으로 단일 허용 source/test 쌍에서 배당 의미 불일치 수락, uncertain 주문/취소 응답 뒤 중복 호출, 또는 확인되지 않은 날짜를 넘는 세션 반환을 재현해야 합니다. 시각 경과나 미래 자료 부재만으로 재호출하지 않습니다.

## 검증·운영 경계

- 실패 verdict와 별도로 local main focused `backend/tests/test_broker_cost_profiles.py` — 42 passed; 변경 파일 Ruff check/format 및 strict mypy, `git diff --check 7f13d33..6c11427` 통과했습니다. 이 검증은 review FAIL을 대체하지 않습니다.
- 금융 provider/data/API·credential·구매·운영 DB·PAPER/live 실행·실주문·remote push는 없었습니다.
- 이 task는 독립적인 WAITING_EXTERNAL입니다. 다른 기존 `lab-discovery-f20488dee5507d82a85c0bfd824c0090`도 review dependency가 해소되지 않아 WAITING_EXTERNAL입니다. roadmap 큐에는 현재 READY/RUNNING이 없습니다.
- `docs/research/portfolio-held-band-preregistration-draft-v2.json`은 `registered=false`, `approved=false`, `execution_allowed=false`, unresolved null 23개 그대로 유지됩니다. held-band FINAL_VALIDATION/OOS는 승인된 preregistration과 적격 미래 자료까지 task-local BLOCKED/PENDING이며, 외부 readiness identity binding은 검증된 producer/validator 계약까지 PENDING입니다.

## 다음 단계

- 현 시점 기준: roadmap 큐는 이 기록 반영 중 잠시 pause, default research queue는 기존 paused입니다. 기록 commit 후 roadmap queue를 재개해 terminal `no_work` 상태와 timer만 확인합니다. source/test, mandate 또는 task-state change나 위에 적은 새 재현이 없다면 같은 discovery를 반복하지 않습니다.
