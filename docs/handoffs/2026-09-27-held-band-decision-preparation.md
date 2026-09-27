# Held-band 결정 준비 handoff

- Updated: 2026-09-27T07:39:39Z
- Workspace: `/home/kwl/projects/jusik`
- Verified main before this handoff update: `5903dc2275c6a47fb2012633770461bdc0724c65`
- 상태: KRX 공식 출처 조사·fixture 프로파일, snapshot read hash guard, artifact read hash guard를 local main에 통합했습니다. 투자 mandate·agent 역할·orchestration·사전등록 조건은 변경하지 않았습니다.

## 완료된 근거

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)는 미정 항목별 권고·근거·대안 영향·provisional 사용범위·승인 경계를 유지합니다. KR 주식 scope가 나중에 선택될 경우 KRX Open API는 일별 가격의 첫 공식 조사 후보입니다. 카탈로그의 과거 제공 기간은 역사적 전체 eligible universe, 당시 관측·수정 시각, strict PIT 및 생존편향 통제를 증명하지 않습니다. API별 관리자 승인·사용 목적 적격성·credential 확인이 필요하고 유료 상품은 실제 비용 승인 전 구매하지 않습니다.
- 기존 KRX prepared fixture의 14,446 universe/bar rows, 194 observed sessions, 94 symbols를 오프라인 프로파일링했습니다. 현재 저장소 calendar 기준 요청기간의 246 sessions 중 174개만 있으며, 72개가 prepared file에 없습니다. 관측범위 내부 calendar gap·중복·일방 membership/bar key·수치 오류는 발견되지 않았습니다. raw manifest와 serialized snapshot이 없어 raw cache integrity와 historical run-to-file binding은 미입증입니다. `available_at`은 collector가 current calendar close로 모델링한 시각이고 provider published/observed time이 아닙니다.
- 보존 run은 `insufficient`, `incomplete`, `readiness.ready=false`, `final_promotable=false`, metric/trade/equity 0입니다. cache는 exposed approximate fixture/debug/pipeline regression 용도만 허용하며 성과, OOS, PIT/data acceptance, 후보·실거래 승인 근거로 사용하지 않습니다. 상세 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-krx-cache-fixture-profile/`.
- `MarketHistoryStore.get_snapshot()`은 복원된 snapshot의 canonical hash와 요청 key를 대조하도록 수정했습니다. 정상 roundtrip, schema-valid artifact/metadata 변조 거부, absent-key `KeyError`를 focused tests로 확인했고 독립 review PASS, main에서 32 tests 통과했습니다. 선택 의존성 및 테스트 파일의 기존 strict mypy 제한은 해당 개발 기록에 분리했습니다.
- `MarketHistoryStore.get_artifact()`은 반환 bytes의 SHA-256을 요청 key와 대조하고 손상 row를 고정 오류로 거부합니다. 정상 bytes/content type, absent-key `KeyError`, corrupted HTTP body refusal을 main에서 33 focused tests로 확인했고 Ruff, store strict mypy, 독립 review PASS입니다. test module strict mypy의 기존 unused ignore 2건은 별도 제한입니다. 상세: [artifact hash 개발 기록](../development-records/2026-09-27-market-artifact-read-hash-binding.md).
- mandate SHA `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1` 유지. v2 unresolved fields 20개는 null이고 `registered=false`, `approved=false`, `execution_allowed=false`입니다.

## 남은 결정과 개별 차단

- 최종 데이터 허용·투자 합격 기준·시장/universe·최종 source·정식 preregistration freeze는 사용자 승인이 필요합니다. 기술적 provisional 기본값은 해당 기준을 동결하지 않습니다.
- `FINAL_VALIDATION`/OOS만 사용자 승인 freeze와 그 뒤 확보한 적격·미노출 미래자료가 생길 때까지 `PENDING/BLOCKED`입니다.
- 새 KRX API 수집에는 API별 관리자 승인, 이용 목적 적격성, 필수 credential 확인이 필요합니다. 현재 credential 상태는 확인하지 않았습니다. 유료 데이터 구매는 지출 승인 전 하지 않습니다.
- 위 항목은 별도 코드 작업을 막지 않습니다. snapshot 및 artifact read hash fix는 완료됐습니다. planner는 `save_artifact()`가 같은 digest key 아래 충돌 bytes가 있어도 성공 digest를 돌려주는 별도 저장 무결성 결함을 `:memory:` SQLite로 재현했습니다. 이 저장 결과를 service가 성공으로 받아들일 수 있고, 새 read guard는 후속 조회를 거부합니다.

## 바로 이어서 할 작업

- 완료 task: `market-artifact-read-hash-binding`, implementation commit `c9533f97b4dbc9c1aca7472e2b75546c18892b6f`, independent review PASS, local main `5903dc2275c6a47fb2012633770461bdc0724c65`에 통합. focused pytest 33 passed, Ruff/store strict mypy/diff check PASS. test-file strict mypy 기존 오류는 개발 기록에 남겼습니다.
- snapshot fix branch `fix/market-snapshot-read-hash-binding`은 clean fast-forward 통합 후 worktree 제거, commit/branch 보존했습니다. 상세 기록은 [snapshot hash 개발 기록](../development-records/2026-09-27-market-snapshot-read-hash-binding.md)입니다.
- 다음 task: `market-artifact-write-conflict-guard`. 동일 bytes 재저장 semantics와 기존 metadata를 보존하면서, 기존 key의 다른 bytes 충돌은 덮어쓰지 않고 fail closed하며 service 계산 함수 호출 전 실패하는지 별도 worktree에서 검증합니다. task 등록부와 provisional assumption을 기록했고 단일 구현자 배정/워크트리 준비가 다음 단계입니다. 사용자 루트 `HANDOFF.md`는 수정하지 않습니다.

## 운영 상태

- 실제 development-runner queue는 `paused=true`입니다. service/timer를 수동 tracked 작업 중 일시 정지했고 현재 둘 다 `inactive`입니다. tracked 문서 통합을 마치면 기존 timer `active` 상태를 복구하되 queue pause는 유지합니다.
- Artifact read fix worktree는 clean 제거했고 branch/commit은 보존했습니다. artifact write-conflict task는 다음 독립 runnable입니다.
- KRX profile worktree는 clean fast-forward 후 제거했고 branch `docs/portfolio-held-band-krx-cache-fixture-profile`와 commit 이력은 보존했습니다.
- root `HANDOFF.md`는 사용자 소유 미추적 파일로 유지하며 읽기·수정·stage하지 않았습니다. remote push, network/API/data collection, purchase, DB/broker/order/PAPER/live 실행은 없습니다.
