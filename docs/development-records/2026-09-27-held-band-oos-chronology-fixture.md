# Held-band 합성 OOS chronology fixture

- 상태: 완료 (오프라인 test-only slice; OOS 평가·qualify 미완료)
- 기록 시각: 2026-09-27T05:15:15Z
- 작업 slug: `portfolio-held-band-oos-chronology-fixture`
- 기준/통합: `0b8700b1500c855f8071c0501f6325587f270bd9` / `f241380ebaf43e0e98450c1d440e8fd60bd0ca2d` (local `main` fast-forward)
- 범위: `backend/tests/test_research_future_observation_replay.py`에만 test-only synthetic chronology fixture를 추가했습니다. production 코드, 승인된 연구 조건, 데이터 허용 기준, 성능 계산은 수정하지 않았습니다.

## 변경과 결정

- 고정 UTC 임시 시각으로 `freeze → event/receipt/read → manifest seal/hash → result open/analyst first access` 순서를 구성했습니다. Manifest는 observation identity·시각·원문 SHA-256을 포함합니다.
- 테스트 전용 `_provisional_stage_ready`는 정상 사례를 통과시키고, freeze 이전 event의 늦은 receipt, 결과 사전 노출, seal 시각/hash 누락, seal 이전 결과 열기, seal 후 manifest 변조를 거부합니다. 실제 `replay()`가 늦은 수신을 `late_arrival`로 분류하는 점과 결과 flag `synthetic=true`, `registered=false`, `accepted_nav=false`, `evaluation_inputs_complete=false`도 확인합니다.
- 이 시간·노출·봉인 표기는 가역적인 provisional test fixture입니다. 실제 접근 제어, 고정된 preregistration contract, 자료 적격성 또는 OOS 승인으로 해석하지 않습니다. 정식 계약과 승인된 적격 자료가 마련되면 대조해 교체하거나 제거합니다.
- 기존 mandate SHA-256 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`를 보존했습니다. v2 `unresolved_before_registration` 20개는 모두 null이며 `registered`, `approved`, `execution_allowed`는 모두 false입니다.

## 문서·계약 영향

- 사용자 문서: 변경 없음. 이 작업은 기존 연구 문서의 테스트 범위 안에서만 이루어졌고 새 투자·자료 허용 기준을 추가하지 않았습니다.
- 운영 문서: [작업 등록부](../worktree-tasks.md)와 [현재 handoff](../handoffs/2026-09-27-held-band-decision-preparation.md)를 갱신했습니다.
- API·설정·데이터 계약: 변경 없음. 기존 v1 artifact, v2 JSON, mandate, 서비스·DB·PAPER/live 상태를 수정하지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_research_future_observation_replay.py` — 격리 worktree 및 통합 후 local `main` 모두 30 passed.
- `backend/.venv/bin/ruff check --no-cache backend/tests/test_research_future_observation_replay.py` 및 `ruff format --check` — 통합 후 통과.
- 통합 후 `backend/.venv/bin/python -m mypy jusik` — 164 source 파일, 오류 없음. 격리 venv에서는 lock에 없는 선택 의존성 `pyarrow`, `torch`의 import 오류가 났으나 canonical `main` venv 검사는 통과했습니다.
- `git diff --check` — 통합 전·후 통과.
- 중앙 `role.review` 사전 routing 검사와 child turn 사후 model audit — `gpt-6-sol`, review 역할 확인. 독립 최종 review — 중대한 지적 없음. 초기 P2는 실패 fixture가 helper 거부를 확인하지 않는다는 지적이었고 공통 test-only predicate assertion을 추가해 해소했습니다.
- 최초 실행에서 사전 노출 시각을 freeze 뒤로 둔 fixture 오류 한 건을 발견해 freeze 이전으로 수정했습니다. 이후 focused 검사 전체가 통과했습니다.

## 안전·운영 상태

- 새 시장자료/API 조회·수집, credential 확인, 외부 지출, OOS/성과 실험, DB·서비스 데이터 변경, PAPER/live 변경, brokerage order, remote push는 하지 않았습니다.
- 수동 저장소 수정 전에 확인한 roadmap runner는 `paused=true`, timer active, one-shot service `activating`이었습니다. timer가 작업 중 서비스를 다시 시작해 tracked 문서 정리가 끝날 때까지 service와 timer를 모두 잠시 stop했습니다. 기존 pause 상태는 바꾸지 않고 timer만 원래 active 상태로 복구합니다.

## 증거와 재개

- 최종 `FINAL_VALIDATION`/OOS task는 사용자 승인 preregistration freeze 뒤의 적격 PIT 및 분석자 미노출 미래자료가 없으므로 계속 `PENDING/BLOCKED`입니다. 이 dependency는 독립적인 무료 source 조사·품질 분석·pipeline·fixture 작업을 막지 않습니다.
- 새 수집은 provider별 필수 credential/access가 생길 때까지, 유료 데이터·서비스는 실제 지출 승인 전까지 blocked입니다. 최종 data grade/source 허용, 시장·universe, 평가 기간·표본·후보 수치, 예산의 투자 기준 동결은 사용자 승인 전까지 하지 않습니다.
- 다음 시작: 적격 후보 자료를 추가 조사하고 현재 local cache의 품질·사용 가능 범위를 read-only로 분석하는 runnable task를 선택합니다. v1/approximate 자료는 개발·debug·회귀 fixture에만 씁니다.
