# 외부 readiness receipt의 오프라인 identity 계약

- 상태: bounded offline contract engineering 완료 (`ENGINEERING_COMPLETE/NOT_EVALUATED`); 운영 readiness 재개 연결은 PENDING
- 기록 시각: 2026-09-27T13:33:23Z
- 작업 slug: `lab-external-readiness-binding-v1`
- 기준/통합: `fe186e60edb1f27c94a3bc0b9f48ff22b1f55c0e` / code `d85f424c03936e5c0c90006f996dab8dbbc97e3c`, registry/docs `b294d944aa24ba849afd2e3e6af74e4083c1aa14`
- 범위: existing external producer/validator와 artifact identity를 바탕으로 오프라인에서 receipt를 검사하는 기술 계약과 회귀 테스트를 추가했습니다. runner/scheduler 연결, 외부 artifact, mandate, preregistration, 투자·자료·OOS acceptance 조건은 바꾸지 않았습니다.

## 조사와 변경

- 기존 source/test inspection receipt는 canonical main의 allowlisted Python source/test hash를 terminal `no_work` 저장 전에 검증하지만, external readiness producer나 receipt identity를 포함하지 않습니다. discovery fingerprint에도 external artifact가 없고 scheduler 재평가 event도 저장되지 않습니다.
- expanded-universe audit의 `offline_validate.py` hash는 provenance의 expected hash와 현재 bytes가 일치합니다. 그러나 `executed_collector_source_hash`는 null이고 validation의 8개 gate는 모두 `BLOCKED`입니다. 기존 legacy artifact를 v1 receipt로 매핑한다면 collector provenance가 없어 `unqualified`이며, 이 해석은 성과·OOS·candidate/실거래 승인 근거가 아닙니다. Legacy artifact에 자동 adapter나 scheduler 연결은 추가하지 않았습니다.
- `backend/jusik/development_runner_readiness.py`는 strict v1 receipt, 독립 task/attempt/scope/criteria와 producer·validator identity/code hash pins, root-relative safe file reads, exact raw receipt SHA 및 별도 semantic digest를 구현합니다. semantic digest는 time/window을 포함한 meaningful criteria, content identity, provenance 및 gate identity/status를 반영하고 timestamp·path·serialization·설명 prose 변화는 제외합니다. 결과 `bound`는 identity/hash 결속 상태일 뿐 gate 승인이나 승격이 아닙니다.
- `backend/tests/test_development_runner_readiness.py`는 missing collector hash와 8개 BLOCKED fixture, malformed/duplicate JSON, stale/mismatched pins, hash mismatch, symlink·경로 이탈·비정규 파일, 의미 digest 변화·metadata 안정성, malformed caller types, artifact count/byte limit, bounded streaming memory를 검증합니다.
- 독립 completion review는 최초에 payload 전체를 보관하는 구조와 malformed argument 예외를 P2/P3로 지적했습니다. 구현 소유자가 content SHA streaming, fail-closed 입력 검사, 자원 상한을 추가했고 수정 commit을 재검토해 PASS했습니다.

## Provisional technical assumptions

- 오프라인 validator의 가역적 resource cap은 receipt 이외 artifact 최대 128개, receipt 포함 전체 최대 256 MiB, 파일별 최대 32 MiB, SHA streaming chunk 64 KiB입니다. 초과는 `invalid`로 끝냅니다. 이는 프로세스 자원 한도이며 데이터 허용 등급·시장/유니버스·최소 표본·후보 수익·위험 한도나 투자 합격 기준이 아닙니다.
- 의미 identity는 task·attempt·scope/request 조건·content·producer/validator pins·정규화된 gate 이름과 상태에 결속합니다. 독립적으로 검증한 producer collector hash가 없으면 `unqualified`로 둡니다. 이 계약은 현재 자료를 적격화하지 않습니다.

## 검증

- `backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_development_runner_readiness.py -c backend/pyproject.toml` — 164 passed.
- `backend/.venv/bin/python -m ruff check backend/jusik/development_runner_readiness.py backend/tests/test_development_runner_readiness.py` — 통과.
- `backend/.venv/bin/python -m ruff format --check backend/jusik/development_runner_readiness.py backend/tests/test_development_runner_readiness.py` — 통과.
- `backend/.venv/bin/python -m mypy --strict --config-file backend/pyproject.toml backend/jusik/development_runner_readiness.py backend/tests/test_development_runner_readiness.py` — 통과.
- `git diff --check fe186e60edb1f27c94a3bc0b9f48ff22b1f55c0e d85f424c03936e5c0c90006f996dab8dbbc97e3c` — 통과.
- 별도 `role.review` 수정본 재검토 — PASS; reviewer도 164개 test와 scoped diff check를 실행했습니다.
- model-routing resolve/check와 helper preflight는 PASS였습니다. child JSONL 파일이 로컬 session directory에 노출되지 않아 routing helper post-audit는 실행할 수 없었습니다.
- 이번 통합 작업에서 broader backend suite는 실행하지 않았습니다. 변경 파일에 한정된 164개 테스트, lint, format, strict type check 및 독립 review를 통과했습니다.

## 안전·운영 상태와 남은 차단

- 시장/provider network·자료 수집·비용·credential·운영 DB/service/queue·PAPER/live·주문·remote push를 사용하거나 바꾸지 않았습니다. latest main을 확인하는 read-only Git fetch는 이 bounded 작업 전 수행돼 있었습니다. source/test/runner queue의 runtime 연결도 추가하지 않았습니다.
- 실제 external readiness event를 runner에 연결하는 부분은 trusted producer가 task/attempt와 collector/validator identity를 publication하고, consumer가 검증할 안정적·원자적 receipt path를 제공할 때까지 PENDING입니다. 현 artifact collector hash null과 8 BLOCKED gate는 유지됩니다.
- held-band `FINAL_VALIDATION`/OOS는 승인된 사전등록과 적격 미래 자료가 마련될 때까지 별도 task-local BLOCKED/PENDING입니다. 미정 필드는 `null`, `registered=false`, `approved=false`, `execution_allowed=false`를 유지합니다.
- §17 priority 4의 static prospective mandate compatibility audit는 기존 자료에서 완료됐습니다. 재등록·수집·평가 실행은 사용자 승인, 적격 자료 및 미사용 evaluation window 없이는 진행할 수 없습니다. 기록 시점에 worktree registry에서 다른 READY task는 확인되지 않았습니다. 기존 manifest-integrity review FAIL/WAITING_EXTERNAL과 그 재시도 금지도 유지합니다. 같은 terminal `no_work` discovery를 반복 호출하지 않았습니다.
- 다음 시작: trusted producer의 publication/atomic path contract가 실제 artifact로 제공되는지 확인한 뒤 receipt를 독립적으로 검증하고, 그때에만 runner fingerprint/scheduler integration을 별도 scope 검토합니다. 그 전까지는 별도 READY 등록 task가 나타날 때만 기존 우선순위로 진행합니다.
- 검증 후 `/home/kwl/projects/jusik-lab-external-readiness-binding` 작업 worktree와 통합된 `feat/lab-external-readiness-binding` branch를 제거했습니다. root의 기존 미추적 `HANDOFF.md`는 보존했습니다.
