# Held-band 결정 준비 handoff

- Updated: 2026-09-27T07:14:40Z
- Workspace: `/home/kwl/projects/jusik`
- Current main: `4319a7f797216811deac0ac846d57b2a64944665` (작업 등록부 갱신 전)
- 상태: KRX 공식 출처 조사와 prepared fixture 프로파일을 통합했습니다. 다음 runnable은 snapshot 저장소의 read-side hash binding guard입니다. 투자 mandate·agent 역할·orchestration·사전등록 조건은 변경하지 않았습니다.

## 완료된 근거

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)는 미정 항목별 권고·근거·대안 영향·provisional 사용범위·승인 경계를 유지합니다. KR 주식 scope가 나중에 선택될 경우 KRX Open API는 일별 가격의 첫 공식 조사 후보입니다. 카탈로그의 과거 제공 기간은 역사적 전체 eligible universe, 당시 관측·수정 시각, strict PIT 및 생존편향 통제를 증명하지 않습니다. API별 관리자 승인·사용 목적 적격성·credential 확인이 필요하고 유료 상품은 실제 비용 승인 전 구매하지 않습니다.
- 기존 KRX prepared fixture의 14,446 universe/bar rows, 194 observed sessions, 94 symbols를 오프라인 프로파일링했습니다. 현재 저장소 calendar 기준 요청기간의 246 sessions 중 174개만 있으며, 72개가 prepared file에 없습니다. 관측범위 내부 calendar gap·중복·일방 membership/bar key·수치 오류는 발견되지 않았습니다. raw manifest와 serialized snapshot이 없어 raw cache integrity와 historical run-to-file binding은 미입증입니다. `available_at`은 collector가 current calendar close로 모델링한 시각이고 provider published/observed time이 아닙니다.
- 보존 run은 `insufficient`, `incomplete`, `readiness.ready=false`, `final_promotable=false`, metric/trade/equity 0입니다. cache는 exposed approximate fixture/debug/pipeline regression 용도만 허용하며 성과, OOS, PIT/data acceptance, 후보·실거래 승인 근거로 사용하지 않습니다. 상세 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-krx-cache-fixture-profile/`.
- mandate SHA `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1` 유지. v2 unresolved fields 20개는 null이고 `registered=false`, `approved=false`, `execution_allowed=false`입니다.

## 남은 결정과 개별 차단

- 최종 데이터 허용·투자 합격 기준·시장/universe·최종 source·정식 preregistration freeze는 사용자 승인이 필요합니다. 기술적 provisional 기본값은 해당 기준을 동결하지 않습니다.
- `FINAL_VALIDATION`/OOS만 사용자 승인 freeze와 그 뒤 확보한 적격·미노출 미래자료가 생길 때까지 `PENDING/BLOCKED`입니다.
- 새 KRX API 수집에는 API별 관리자 승인, 이용 목적 적격성, 필수 credential 확인이 필요합니다. 현재 credential 상태는 확인하지 않았습니다. 유료 데이터 구매는 지출 승인 전 하지 않습니다.
- 위 항목은 별도 코드 작업을 막지 않습니다. planner가 발견·재현한 `market_history_store.get_snapshot()`의 lookup-key/body canonical hash 불일치는 synthetic fixture와 temporary test DB로 수정·검증할 수 있습니다.

## 바로 이어서 할 작업

- 등록 task: `market-snapshot-read-hash-binding`. 기준 저장소 `docs/worktree-tasks.md`를 읽고, 독립 worktree `/home/kwl/projects/jusik-market-snapshot-read-hash-binding`과 `fix/market-snapshot-read-hash-binding`에서 단일 `code_small` 구현 담당자를 배정합니다.
- 범위는 `backend/jusik/market_history_store.py`의 `get_snapshot()` read-side identity guard와 `backend/tests/test_market_research.py`의 mismatch/roundtrip/absent-key regression tests입니다. 잘못 결속된 과거 KRX export의 복원, migration, market/data acceptance는 범위 밖입니다.
- 구현 후 별도 review, focused pytest, Ruff, configured strict mypy, 통합 main 검증, development record와 이 handoff 갱신을 수행합니다. 사용자 루트 `HANDOFF.md`는 수정하지 않습니다.

## 운영 상태

- 실제 development-runner queue는 `paused=true`입니다. 추적 문서 통합 중 service/timer를 일시 정지했고 둘 다 현재 `inactive`입니다. 저장소 작업을 마친 뒤 기존 timer `active` 상태를 복구하되 queue pause는 유지합니다.
- KRX profile worktree는 clean fast-forward 후 제거했고 branch `docs/portfolio-held-band-krx-cache-fixture-profile`와 commit 이력은 보존했습니다.
- root `HANDOFF.md`는 사용자 소유 미추적 파일로 유지하며 읽기·수정·stage하지 않았습니다. remote push, network/API/data collection, purchase, DB/broker/order/PAPER/live 실행은 없습니다.
