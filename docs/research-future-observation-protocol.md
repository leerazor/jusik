# 미래 관측 프로토콜 설계 초안

이 문서는 2026-09-12T00:00:00Z 기준으로 `future-observation-protocol-v1-draft-63c4e3f2380b4e149d60d17db90459c7`라는 별도 초안 프로토콜의 버전 `0.1-draft`를 정의한다. 초안 ID와 버전은 설계를 식별하기 위한 값이며 등록 완료, 수집 시작, 평가 가능 또는 통과를 의미하지 않는다. 등록부 파일을 만들거나 기존 등록을 변경하지 않는다. 이 기준 시점에 runtime 등록 파일과 capture artifact는 조회하지 않았다.

## 목적과 적용 범위

목적은 등록이 끝난 뒤 새로 도착하는 관측을 수신 시각, 원문 보존, 출처 연결과 결손 상태까지 재현 가능하게 기록하는 것이다. 관측의 미래 가용성과 provenance 검증, 경계 NAV 승인, 성과 평가는 서로 다른 단계로 취급한다. 이 문서는 그 단계의 경계와 보류 조건을 정한다.

기존 PAPER 계약의 평가 창 `2026-09-14T00:00:00Z`부터 `2026-11-09T00:00:00Z`까지는 기존 `research_prospective_registration` 계약에 속한다. 이 초안 프로토콜에 그 기간을 배정하지 않으며, 기존 session·source run·정책·코드 identity·DB·경계 artifact의 소유권이나 의미를 바꾸지 않는다. 이 초안이 등록되더라도 고정 PAPER 창을 재사용하거나 새 창으로 해석하지 않는다.

후향 자료, 합성 자료와 이 프로토콜의 전향 자료는 물리적 디렉터리와 집계에서 분리한다. 권장 audit 경로는 다음과 같다.

```text
future-observation-protocol-v1-draft-63c4e3f2380b4e149d60d17db90459c7/
  manifest/       # protocol ID/version과 등록 계약
  retrospective/ # 과거 시각 자료와 재구성 결과
  synthetic/      # 합성 quote·receipt·journal 입력
  prospective/    # 등록 후 수신된 관측의 목록과 상태
    raw/          # 변경하지 않는 원문 artifact
    derived/      # 검증·집계 결과
    missing/      # 결손, 중단, 제한 초과 기록
  review/         # 사람이 확인한 provenance와 검토 기록
```

`retrospective`와 `synthetic`의 행·파일·건수는 `prospective` 표본 수, 경계 NAV, 미래 성과 또는 통과율에 합산하지 않는다. 과거 event 시각을 가진 자료를 나중에 받았더라도 수신 전의 전향 가용 자료로 소급하지 않는다.

## 등록 전 게이트

수집을 시작하려면 하나의 불변 manifest에 다음 값을 채우고 canonical JSON과 SHA-256을 보존해야 한다. 값이 하나라도 비어 있거나 합의되지 않은 상태는 `unregistered`이며 관측을 전향 표본으로 세지 않는다.

| 필드 | 등록 시 요구 | 현재 초안 상태 |
| --- | --- | --- |
| protocol ID/version, 등록 시각 | 고유 ID, 버전, aware UTC 시각 | 초안 식별자만 정함; 미등록 |
| 모집단과 symbol/universe | 대상, 제외 대상, 변경 규칙 | 미정; 미등록 |
| source와 수집 방법 | 제공자, 읽기 경로, 읽기 전용 권한과 identity | 미정; 미등록 |
| 수집 기간과 빈도 | UTC start/end, poll 또는 event 주기 | 미정; 미등록 |
| 가격·FX 선택 규칙 | cutoff, revision, 통화 변환과 stale 제한 | 미정; 미등록 |
| 필수 필드와 provenance | event/market/received 시각, 원문, 출처 연결 | 설계 중; 미등록 |
| 누락·지연·정정 규칙 | 결손, late, revision, 중단의 처리와 종료 조건 | 이 문서에서 상태 규칙만 정의; 미등록 |
| 평가 정의 | NAV·성과·비교군·필수 경계 증거 | 미정; 미등록 |
| 코드·입력 identity | 코드, 달력, source manifest/result와 입력 hash | 새 계약으로 고정하지 않음; 미등록 |

등록은 위 필드, 시작 전 manifest hash, 저장 경로와 보존 정책, 검토자와 승인 기록이 모두 존재할 때만 `registered`로 전환한다. 시작 후 모집단·주기·선택 규칙·기간을 바꾸면 기존 기록을 수정하지 않고 새 protocol version과 새 시작 구간을 등록한다. 등록 전 수집분은 prospective가 아니라 미분류 입력으로 보존한다.

## 수신 구간과 관측 레코드

등록된 기간의 포함 규칙은 실제 수신 시각 `received_at`을 UTC로 정규화한 반열린 구간 `[start, end)`이다. `received_at == start`는 포함하고 `received_at == end`는 제외한다. `event_at` 또는 `market_at`만으로 포함 여부를 정하지 않으며, timezone 정보가 없는 시각은 유효 관측으로 등록하지 않는다. 각 레코드는 다음을 함께 보존한다.

- protocol ID/version, source identity, 관측 ID, symbol과 event/market 시각
- 원문 raw bytes, 원문 경로, 원문 크기와 SHA-256; normalized/canonical derivative는 별도
- 읽기 시작·종료 시각(`read_started_at`, `read_finished_at`)과 수신 시각
- parser/schema version, 연결된 입력·quote·FX provenance ID와 hash
- 상태, 오류 코드, 중복·충돌·late·revision·missing·clock·truncation 표지

원시 artifact는 실제 수신한 raw bytes 그대로 append-only로 저장하고 hash가 바뀐 파일을 덮어쓰지 않는다. canonical JSON이나 parser가 만든 typed payload는 raw bytes와 별도의 derivative로 저장하고 서로의 원문을 대체하지 않는다. 내용 hash는 저장 bytes의 변경 검출값이며 출처의 진위, 독립적인 타임스탬프 또는 당시 공개 사실을 단독으로 증명하지 않는다. 읽기 구간은 원장 commit 시각으로 표현하지 않는다.

## 중복과 예외 처리

동일 source와 관측 ID가 같은 원문 hash로 다시 도착하면 최초 실제 수신 시각과 raw bytes를 불변으로 보존하고, 반복 수신 사실은 별도 receipt로 남기되 집계의 논리 관측은 한 건으로 센다. 나중의 반복 수신은 최초 관측을 수신 구간 안으로 이동시키지 않는다. 같은 ID에 다른 원문이 오면 `conflict`로 모두 보존하며 먼저 저장된 값을 덮어쓰거나 선택하지 않는다. 내용 변경이 source revision으로 명시되면 새 revision 레코드로 append하고 이전 revision과 유효 시각을 연결한다. 나중에 도착한 과거 event는 `late_arrival`로 표시하며 과거 시점에 알려졌다고 소급하지 않는다.

해당 시각이 아직 오지 않은 경계는 `not_due`로 기록하며 결손으로 세지 않는다. 경계가 도래했거나 수신 구간이 닫힌 뒤 필수 관측 또는 경계 artifact가 없으면 `missing`으로 기록한다. 읽기 실패·미래 source 자체의 미가용·원문 손상은 `unavailable`로, 원문은 있으나 source·시각·선택 근거를 확인하지 못한 경우는 `unverified_provenance`로 구분한다. 시계가 역행하거나 UTC 변환이 불가능하면 해당 레코드를 유효 표본으로 세지 않고 `clock_invalid`를 남긴다. byte·행·표본 제한으로 일부만 읽었으면 `truncated`와 전체·읽은·미검사 건수를 함께 남긴다. 종료 시점에 남은 결손, 충돌, 지연, 정정과 제한 초과는 결과의 일부이며 유리한 기간으로 교체하지 않는다.

## 현재 코드와 경계 증거의 의미

현재 prospective registration은 별도의 고정 PAPER 계약을 56일 창과 identity hash로 묶고, readiness는 정확한 경계 checkpoint가 없으면 `missing`, 있더라도 `unverified_candidate`로 표시한다. fill readiness는 `received_at` 기준 `[start, end)`를 사용하고 검사 상한을 넘으면 `truncated`와 `incomplete`를 유지한다. 0건은 `unobserved`이며 성공이나 통과가 아니다.

raw boundary capture는 allowlist 원장 행, 입력 version, quote, checkpoint와 읽기 시점 최신 관측을 canonical artifact와 자체 SHA-256으로 보존한다. 이 artifact는 실제 read-time raw observation이며 정확한 경계 시점 상태나 승인 NAV를 보장하지 않는다. boundary evidence는 artifact가 없거나 읽을 수 없는 경우 `missing` 또는 `unavailable`, 검사한 경우 `inspected`로 구분하며 결과의 `accepted_nav`와 `evaluation_inputs_complete`는 false로 고정한다. `latest_at_read_time` 관측을 경계 가격으로 바꾸지 않고, 현재 DB의 값으로 과거 결손을 보완하지 않는다.

격리된 receipt journal은 payload hash, idempotency, 가시성 receipt와 process clock을 보존하는 실험이다. `isolated_experiment`, `production_ledger_linked=false`, `accepted_nav=false` 계약이므로 PAPER 원장, 실제 체결, 전향 평가의 증거로 승격하지 않는다. receipt가 없거나 시계가 유효하지 않은 경우에도 entry commit 여부를 구분해 남긴다.

## 보류해야 하는 주장

다음 세 상태를 같은 `missing`으로 뭉뚱그리지 않는다.

1. **미래 자료 미가용**: 아직 수신 시점이 오지 않았거나 source·경계 artifact가 제공되지 않아 확인할 수 없다. 이는 관측이 없다는 사실이지 실패나 성공이 아니다.
2. **provenance 미검증**: 원문 또는 후보 값은 있지만 source identity, 공개 시각, 선택된 FX·가격, 원장 연결을 확인하지 못했다. hash 일치만으로 해결되지 않는다.
3. **운영 파일 미조회**: 이 작업에서 runtime 등록 파일, PAPER DB, boundary capture 파일과 원격·GPU 상태를 조회하지 않았다. 존재·부재·정상 상태를 추정하지 않으며 조사했다는 기록으로 바꾸지 않는다.

이 문서는 미래 표본, 경계 NAV, 수익률, 손실 제한 준수, 통계적 유의성, 평가 pass, PAPER 승격 또는 주문 가능성을 주장하지 않는다. 필수 등록값과 원시 증거가 모두 확보되고 독립 검토가 끝날 때까지 `accepted_nav=false`와 `evaluation_inputs_complete=false`를 유지한다. 미래 자료가 제공되더라도 provenance·경계·정정·결손 검토가 끝나기 전에는 성과를 계산하지 않는다.

2026-09-12T00:00:00Z 현재 다음 근거는 확보·승인되지 않았다. 미래 start/end 경계 증거와 완료된 prospective 표본, 승인 가능한 NAV와 선택 가격·FX provenance, 실제 체결에 선택한 FX 원문과 원장 변화의 원자적 연결, 기업행동·배당 권리·세금·총수익률 coverage, 미래 휴장·특별장 예외, 호가 깊이·부분 체결·시장 충격 근거, 나중에 수집한 자료로는 성립하지 않는 historical point-in-time vintage가 여기에 포함된다. 이 목록은 자료가 존재하지 않는다는 단정이 아니라 현재 승인 상태가 미확정이라는 기록이다.

## 변경 제한과 종료 조건

이 초안 작업에서는 등록부, PAPER DB·engine·GPU·원격 서비스, 수집 실행과 운영 파일을 변경하지 않는다. 새 protocol 디렉터리를 실제로 만들거나 데이터를 읽는 것도 등록과 별도 실행 승인이 있기 전에는 하지 않는다. 등록 후 종료는 `[start, end)`의 경계가 닫히고, 모든 원시 artifact와 hash manifest가 보존되며, 결손·충돌·revision·late·clock·truncation 목록과 provenance 검토 결과가 남을 때만 가능하다. 종료 파일이 있다고 해서 평가 pass를 선언할 수 없다.
