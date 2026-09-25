# Paper execution journal 동시 조정 경합 수정

- 상태: 완료
- 기록 시각: 2026-09-25T07:34:56Z
- 작업 slug: `lab-paper-execution-restart-journal-race`
- 기준/통합: `315e983` / `ee93703`
- 범위: 오프라인 SQLite journal의 부분체결 단조성 및 자동 개발 증거 경로를 복구했다. 실제 브로커 adapter, PAPER/live 활성화와 투자 판정은 변경하지 않았다.

## 변경과 결정

- 초기 자식은 journal 코드를 병합했지만 완료 증거가 작업용 worktree 파일을 가리켜 `completion_invalid`로 실패했다. 두 소유 파일의 제출 SHA-256은 당시 main과 일치했으나 실패 attempt는 수정하거나 소급 완료하지 않았다.
- 별도 Sol 검토가 두 원장의 늦은 갱신으로 영속 체결 수량 5가 3으로 줄어드는 P1을 임시 SQLite에서 재현했다. `backend/jusik/paper_execution_contract.py`의 authoritative read·상태 전이 검증·UPDATE를 `BEGIN IMMEDIATE` 한 트랜잭션에 묶었다. 브로커 호출은 트랜잭션 밖, 메모리 캐시 갱신은 commit 뒤다.
- `backend/tests/test_paper_execution_contract.py`에 두 ledger의 결정적 경합·오래된 부분체결 거부·최신 체결 보존 테스트를 추가했다. 제품 소유 브랜치 `63700c1`을 자동 자식이 local main `ee93703`에 통합했다.
- `backend/jusik/development_runner.py`는 공학 자식에 통합 후 canonical main 소유 파일 절대 경로를 완료 증거로 제출하도록 지시한다. 재시도 지시는 실제 이전 attempt가 있을 때만 붙고, P1 지시는 이 spec에만 붙는다. 기존 runner validator·reviewer 계약은 완화하지 않았다.
- 기존 FAILED 작업을 `retry`로 새 attempt에 넣었다. 이전 실패 이력·완료 JSON은 그대로 남았다. 새 시도 `67c0ee02d4c5405e928191539814a47b`는 main 두 파일 증거와 정확한 baseline diff를 통과해 `WAITING_EXTERNAL`이 됐다. 독립 review `77eef7c4613548ba9f9cac4d86440f38`은 `PASS`; DB 최종 상태는 `DONE + ENGINEERING_COMPLETE + NOT_EVALUATED`다.

## 문서·계약 영향

- 사용자 문서: 화면 동작 변화가 없어 해당 없음.
- 운영 문서: `docs/development-runner.md`에 공학 증거 경로·재시도 브랜치 조건을 반영했다. `docs/worktree-tasks.md`에 실제 시도·검토·워크트리 상태를 반영했다.
- API·설정·데이터 계약: journal이 동시 조정 중에도 기존 단조 체결 상태를 보존한다. DB schema, 투자 검증 기준, 실제 주문 경계는 변경하지 않았다.

## 검증

- 제품 브랜치에서 기존 코드 경합 RED를 재현하고 수정 뒤 `test_paper_execution_contract.py` 23개 통과. local main 통합 후 같은 23개, Ruff check/format, strict mypy 통과.
- runner 안내 브랜치·local main에서 관련 pytest 165개, Ruff check/format, strict mypy 통과. 별도 Sol 검토의 P2 지적을 수정·재검토 PASS했다.
- 별도 Sol 제품 코드 검토: P1 수정 PASS. 운영 review receipt `PASS`와 DB 공학 완료를 확인했다.
- 프런트엔드 변경이 없어 build는 실행하지 않았다. 실제 브로커·전원 손실 실험은 범위 밖이다.

## 안전·운영 상태

- 수동 수정 중 runner pause, service inactive, timer active를 유지했다. 검증 뒤 기존 FAILED task만 retry하고 service를 시작했다. 문서 갱신을 위해 다시 pause한 상태다.
- 운영 runner DB는 기존 시도를 보존했다. 재시도 전 일관된 백업은 아래 audit에 보존했다. DB를 수동 UPDATE하거나 실패 JSON을 수정하지 않았다.
- 실주문, PAPER/live activation, 투자 검증 승격, 추가 결제, credential/권한 변경, 원격 push 없음.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-continuous-engineering-backlog/`; 재시도 전 DB 백업 `runner-before-paper-race-retry.db` SHA-256 `c22cea517d191007b23487d01838fd991a9918f9577b78bfcb6d135fdd1994f0`.
- 남은 작업: docs/handoff 반영 후 runner resume. 자동 backlog는 소진됐으므로 다음 사전 검토된 READY 작업을 별도로 준비해야 한다. 투자 검증은 `NOT_EVALUATED`다.
- 다음 시작: runner status에서 READY/WAITING과 소진 사유를 확인하고 독립된 다음 spec을 고른다.
