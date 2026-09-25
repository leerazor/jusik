# 실패한 공학 후보의 제한된 독립 검토 복구

- 상태: 완료
- 기록 시각: 2026-09-25T08:36:23Z
- 작업 slug: `lab-engineering-failed-candidate-recovery`
- 기준/통합: `4c888d9` / `8aef418`
- 범위: 제품 커밋은 이미 main에 있으나 완료 형식 오류로 FAILED가 된 좁은 공학 시도의 별도 검토 후보를 생성한다. 일반 완료 게이트·투자 상태는 변경하지 않는다.

## 변경과 결정

- `backend/jusik/development_runner.py`에 paused 상태에서만 가능한 `recover-failed-candidate` 운영 명령을 추가했다. 원 시도 baseline, 정확한 제품 소유 파일 diff, 커밋 조상관계와 현재 소유 파일 불변성을 재검증한다.
- 원본 JSON의 `waiting_external`/blocker 없음/사유 없음과 미검토 테스트 통과 후보만 허용한다. 동일 바이트로 파싱·SHA를 계산하고 운영자가 현재 SHA를 명시한다. 기존 실행 transcript의 최종 메시지 일치와 해시도 묶는다.
- `backend/jusik/development_runner_store.py`는 원본 FAILED 행을 보존하고 새 복구 후보를 CAS로 생성한다. `development_runner_review.py`의 receipt는 복구 제품 커밋을 추가 결속하며 별도 PASS만 공학 완료로 확정한다.
- Sol 독립 검토의 parse/hash TOCTOU P1을 수정하고, 원본·transcript·교정 후보를 reviewer 전후와 최종 전이에서 재검증했다.

## 문서·계약 영향

- 운영 절차: `docs/development-runner.md`에 명령, DB 백업, SHA pin, 독립 검토와 한계를 기록했다.
- DB schema migration 없음. 기존 FAILED 행을 지우거나 바꾸지 않는다. 별도 복구 후보와 receipt만 추가한다.
- 과거 시도에는 실패 당시 암호학적 해시가 없다. 현재 SHA pin과 transcript 대조는 복구 시점의 일치만 증명하며 과거 불변성을 증명하지 않는다.

## 검증

- runner 관련 pytest 134개, Ruff check/format, 변경 소스 3개 strict mypy 및 diff check 통과. 원본 A→B 치환, 잘못된 SHA, transcript·후보 변조 거부를 포함한다.
- local main의 관련 runner·제품 pytest 122개, Ruff check/format, strict mypy 통과. 별도 Sol 최종 검토 PASS, P1/P2 잔여 없음.
- 운영에서 `recover-failed-candidate`로 후보 `6d2f375c0bab42e4aee911d4cb84a440`를 생성하고 독립 review `afc2886778ed4db1a0912ff9d155027e` PASS 후 공학 완료를 확인했다. 원본 실패 시도는 그대로 남았다.

## 안전·운영 상태

- 운영 DB를 SQLite online backup 후 복구했다. 백업 integrity check `ok`, SHA-256 `a23ca1c3ff65924ecef3f04bfcdc5468a18779557b8de9bfb21d22f059f37bc6`.
- 실주문·PAPER/live activation·원격 push·추가 결제·credential/권한 변경 없음. 문서 기록 동안 runner pause·service inactive, timer active다.

## 증거와 재개

- 백업: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-continuous-engineering-backlog/runner-before-failed-candidate-recovery.db`.
- 다음 시작: runner를 재개하고 유한 backlog 소진/다른 READY 상태를 확인한다. 향후 FAILED 시점 출력 SHA의 즉시 영구 기록은 별도 개선 후보이며 현재 legacy 시도의 과거 불변성을 소급 증명하지 않는다.
