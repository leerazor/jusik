# 구현 완료 reviewer의 일시 호출 장애 복구

## 근거와 제한한 범위

3시간 성능 개선 작업의 후속이다. 기존 `_run_review`는 child 비정상 종료를 모두
`codex_exit`로 기록하며, store의 재검토 선택은 timeout·idle timeout·restart만
허용한다. 확인 가능한 공급자 일시 장애도 후보를 다시 선택하지 못하게 만들 수 있다.
기존 discovery에는 구조화된 오류 분류·영속 backoff가 있으므로 그 정책을 재사용한다.

단일 구현자는 runner/store와 기존 review 테스트·새 transport 테스트 네 파일만
소유한다. 일반 engineering과 같은 구현 완료 경로를 쓰는 roadmap code 작업을
포함한다. 연구 scope reviewer는 TTL·snapshot·별도 상태 및 구버전 reader 문제가
있으므로 이번 변경에서 제외한다. 자동개발 전체가 복구됐다고 해석하지 않는다.

구현 중 범위를 한 줄 확장했다. 기존 `test_development_runner_recovery.py`의
`test_recorded_digest_final_review_cas_rejects_marker_tampering`은 paused 복구 fixture에서
직접 review claim을 전제했다. root가 이 사실을 확인하고 `_recover` 성공 후
`store.resume()` 한 줄만 추가하도록 승인했다. 이 테스트의 목적은 marker 변조 CAS
검사이며 pause 우회가 아니다. 새 원자 pause 검사는 유지하고 보호 assert는 바꾸지 않는다.

## 승인한 구현 계약

- 실제 child와 process group의 종료가 확인된 비정상 종료만 기존 제한된 구조화
  `turn.failed` 분류기로 검사한다. 임의 text·stderr·성공 출력은 근거가 아니다.
- `review_attempts`에 nullable `retry_kind`, `retry_after`와 기본 0인
  `transient_failures`를 가산한다. 알려진 5개 종류만 새 `review_transport_<kind>`
  실패 코드와 같은 완료 transaction에서 저장한다. 과거 이력을 재분류하지 않는다.
- 알려진 전송 장애는 5/15/60분, auth는 6시간 뒤 재시도한다. 이 새 metadata가 유효한
  시도만 기존 비전송 시도 2회 상한에서 제외한다. 실제 호출은 계속 quota와 cooldown을
  소비하며, 무효 결과·거절·불명 오류·기존 timeout/restart의 제한은 유지한다.
- 선택과 원자 claim이 같은 판정을 사용한다. 잘못된·누락된·UTC가 아닌 기한은 거부하고,
  pause·최신 attempt·후보 identity·중복 running도 다시 확인한다. 다른 READY와 공학
  fallback은 기다리는 후보 때문에 중단하지 않는다.

## 다른 작업의 커밋과 검토 identity

일반 최초 검토는 현재 main이 제품 commit과 같아야 한다. 이 기존 규칙과 회귀 검사는
보존한다. 단, 새 opt-in transport anchor가 확인된 재시도에는 이미 존재하는 historical
검증을 제한적으로 재사용한다. 이것은 기존 동작의 제한적 확장이며 일반 stale 후보의
자동 복구나 투자 gate 완화가 아니다.

원 implementation attempt·baseline·제품 commit·completion 전체·recovery provenance·
소유 파일 hash를 고정한다. 제품 commit과 이전 검토 HEAD는 새 main의 조상이어야 하고
제품 commit 및 현재 main의 소유 blob은 같아야 한다. 최초 anchor와 후속 anchor는
제품 identity로 정규화한다. 매 시도에는 fresh HEAD와 새 review ID를 결속한다.
따라서 소유 범위 밖의 독립 작업이 A→B를 commit한 뒤에도 제품 A를 B에서 별도 검토할
수 있지만, 파일·증거·제품 교체나 검토 진행 중 B→C 변경은 거부한다. 현재 실행의
정확한 context와 독립 PASS 검증은 생략하지 않는다.

## 데이터 보존과 되돌리기

전진은 가산 schema와 새 실패 코드만 사용한다. 구버전은 새 실패 코드를 허용하지
않으므로 기한 전후 모두 해당 후보를 보류하며 독립 READY를 계속 처리한다. rollback은
코드 버전을 되돌릴 뿐 DB 열·행을 삭제하거나 새 실패를 timeout으로 위장하지 않는다.
새 버전으로 돌아오면 원 deadline을 재사용한다. 실제 이전 버전 store를 임시 DB에서
실행하여 이 제한을 검증한다. 운영 DB backup 및 기존 행의 보존 검사는 root만 수행한다.

## 완료 기준과 현재 상태

구현 기준은 `d30c809`이며 전용 worktree의 제품 commit은
`ff9395890c1889fac652e349213e955920f607c7`이다. 239개 집중 pytest, 소유 5파일의
Ruff check/format·strict mypy·diff 검사를 통과했고 별도 Sol review 중이다.
root가 보존한 운영 DB의
online backup은 audit `review-transport/runner-before-review-transport.db`,
SHA-256 `f9416377bb8e0b568ed656c651f71694ab0d52b3095441e09e0fc909036204a4`,
13개 table·integrity `ok`다. 구현자는 이 운영 backup을 사용하지 않고 합성 fixture로
검사한다. fake CLI·clock으로 RED/GREEN을 확인하고, 반복 장애
5/15/60/60분·auth 6시간, restart, 정확한 due 경계, 다른 READY/fallback, 원자 중복 claim,
pause/quota/cooldown, 위조 text·oversize·REJECT·무효 receipt·불확실 orphan,
소유 hash/HEAD 변경과 별도 PASS 전 미완료를 확인한다. legacy 행 보존·반복 초기화·
SQLite integrity·구버전 rollback 및 집중 검사·독립 Sol review·main 검증까지 완료해야
`ENGINEERING_COMPLETE/NOT_EVALUATED`로 기록한다.

root의 별도 migration 검사도 운영 DB가 아니라 보존 backup의 새 복사본에서 수행했다.
13개 table·1,322개 기존 행의 모든 기존 열 값을 첫·반복 초기화 뒤 대조하여 보존을
확인했다. review의 세 가산 열 외 schema 변경은 없고 20개 과거 review의 metadata는
NULL/NULL/0이며 재분류되지 않았다. 원 backup SHA와 SQLite integrity `ok`도 유지됐다.
재현 script·증거는 audit `review-transport/verify_db_preservation.py`,
`DB_PRESERVATION.md`에 있다. 운영 적용 또는 실제 공급자 장애 복구를 증명한 것은 아니다.

독립 Sol 검토는 첫 transport 이전의 timeout 검토 HEAD가 anchor에서 빠지는 P2를
재현했다. 제품 A의 서로 다른 후손 B/C 중 B에서 먼저 검토한 뒤 C에서 transport를
겪으면 이전 B의 ancestry 없이 완료될 수 있었다. 후속
`010e274ace06c042d5b6ce281b87acdc9702fd8b`에서 opt-in transport가 있을 때 모든 과거
검토의 identity·HEAD를 포함하도록 수정했다. 정상 선형 이력, sibling 분기 거부,
이전 context 변조 거부 회귀를 추가하고 pure legacy 선택은 유지했다. 구현자 affected
pytest 154개와 Ruff·strict mypy PASS, 독립 검토자의 최초 transport 59개 및 후속
선별 16개 PASS 후 조치할 결함 없음으로 재검토됐다.

local main은 runner lock·pause·실행 attempt 0·소유 경로 무변경 확인 뒤
`3814b6f1912250c88b90f61251589a3a74331858`로 통합했다. 병합 직전 main은
`53d94762c9f4c9276c211eff9d60305cdbdd6d20`이다. main 집중 pytest 242개(139.95초),
소유 5파일 Ruff check/format·strict mypy PASS로 `ENGINEERING_COMPLETE/NOT_EVALUATED`다.
JUnit은 audit `review-transport/main-focused.xml`이다. 별도
`research-novice-comprehension` UI 수동 작업과 pause를 공유하므로 아직 재개하지 않는다.

실제 provider 장애를 유발하지 않고, credentials·권한·과금·실주문·투자 기준·자동
scope 승인·과거 산출물은 변경하지 않는다. 위 소유 범위를 넘는 구조 변경이 필요하면
구현자가 임의 확장하지 않고 감독자에게 근거를 반환한다. 전체 sprint 종료는
2026-09-26T10:56:14Z이며 본 구현은 검토 시간을 남기도록 60분 이내 반환을 목표로 한다.
