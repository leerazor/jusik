# 전체 회귀 provenance pin 재검증

- 상태: 차단 원인 확인
- 기록 시각: 2026-09-20T06:00:00Z
- 작업 slug: `full-regression-provenance-recheck-20260920`
- 기준/통합: `de0723c` / 문서 기록 커밋
- 범위: backend 전체 회귀를 backend 패키지 경로에서 실행하고, 고정 archive와 현재 코드의 불일치를 분류했습니다. archive, 결과, 계산기, production guard는 수정하지 않았습니다.

## 변경과 결정

- 전체 회귀는 `1702 passed, 6 failed, 2 warnings`였습니다.
- 실패는 `engine_source_mismatch` 3건, guarded variant SHA mismatch 1건, corrected performance envelope가 같은 engine mismatch로 중단되는 1건, frozen signal archive의 calendar/imported-code hash mismatch 1건입니다.
- 이는 현재 코드와 과거 고정 artifact의 provenance identity가 다르다는 fail-closed 결과입니다. 과거 artifact를 덮어쓰거나 pin을 갱신해 성공으로 위장하지 않습니다.
- 투자자 freshness 회귀는 이전 작업에서 고정해 전체 실패 수에 다시 포함되지 않았습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. historical evidence의 재해석을 하지 않았습니다.
- 운영 문서: runner/service/timer 상태는 변경하지 않았습니다.
- API·설정·데이터 계약: 변경 없음. 경제 acceptance와 PAPER/live 승격은 차단 유지입니다.

## 검증

- `backend/.venv/bin/python -m pytest -q` (cwd `backend`) — `1702 passed, 6 failed, 2 warnings`.
- 실패 유형은 `engine_source_mismatch`, variant SHA, calendar/imported-code SHA로 분류하고 `/tmp/jusik-full-pytest.log`에서 확인했습니다.
- 두 portfolio bundle manifest가 요구하는 engine SHA `2a91ef9621fcb96b52179fb8fd22df7f74d6aab385b798333dd354594e61f70c`는 Git commit `cb1d12f2e68d370985f0e5b167a9f443edbcee88`와 audit snapshot에 보존되어 있습니다. signal archive의 calendar SHA `edca750738bf69bb58b27ee15a0985a3434707ba1daad06719c26a4d17a54d9a`는 Git commit `c67e6e271bcb5276ab450c82965752fbd9a08364`와 archive source에 보존되어 있습니다. 현재 checkout에 자동 주입하지 않았으며, 현재 코드와 섞지 않는 별도 격리 replay가 필요합니다.
- 개별 canonical contract bundle `243 passed`, governance/runner/mandate bundle `117 passed`, strict mypy `150 source files`는 별도로 통과했습니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·네트워크 수집·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 상태를 유지합니다.

## 증거와 재개

- audit: `/tmp/jusik-full-pytest.log` (작업 세션 로컬 로그)
- 남은 작업·차단 조건: 고정 archive를 재사용하려면 당시 source snapshot을 복원하거나 별도 새 evidence bundle을 만들어 독립 review해야 합니다. 현재 실패를 무시하고 경제 성과를 주장하지 않습니다.
- 다음 시작: archive별 승인된 source snapshot/manifest를 read-only 대조하고, 복원 근거가 없으면 해당 historical test를 차단 기록으로 유지한 채 R1/R2 자료 gate를 우선합니다.
