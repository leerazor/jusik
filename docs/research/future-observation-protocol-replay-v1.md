# 미래 관측 프로토콜 합성 replay v1

기준 설계는 [미래 관측 프로토콜](../research-future-observation-protocol.md)이다. 이 도구는 그 상태 분류를 오프라인 합성 입력으로 재현한다. 등록, 수집, DB, PAPER 엔진, NAV, 주문과 연결하지 않는다. 출력은 항상 `synthetic=true`, `registered=false`, `accepted_nav=false`, `evaluation_inputs_complete=false`이다.

## 입력 계약

`SyntheticFixture` JSON은 `synthetic: true`를 반드시 포함한다. `false`, 누락, 문자열 `"true"`는 거부한다. `window_start_at`, `window_end_at`, `checked_at`과 각 관측의 `source_id`, `observation_id`, UTF-8 문자열 `raw`, `received_at`, `event_at`, `read_started_at`, `read_finished_at`이 필요하다. 모든 시각은 timezone-aware여야 한다. 관측 배열의 순서가 receipt 순서이며 도구가 정렬하지 않는다.

선택적으로 `evidence_flags`에 `unavailable` 또는 `unverified_provenance`를 기록하고, `required_boundaries`에 `boundary`, `due_at`를 기록한다. boundary requirement 자체가 해당 증거가 없음을 선언하는 합성 입력이다. `checked_at < due_at`은 `not_due`, 그 이후는 `missing`이다. start/end 요구사항은 각각 한 번만 둘 수 있고 due 시각은 window 경계와 같아야 한다. DB readiness나 receipt journal을 재사용하거나 조회하지 않는다. `truncation`의 `inspected_count`는 실제 observations 길이와 같아야 하며 미검사 수를 계산한다.

## 분류와 보존

수신 구간은 UTC 기준 `[window_start_at, window_end_at)`이다. 각 receipt의 `available_at_check`는 parsed `received_at <= checked_at`일 때만 true이며, 미래는 false, 수신 시각 오류는 null이다. 이는 표본 승인이나 provenance 검증이 아니다. `event_at`이 구간 시작보다 이른데 수신은 구간 안이면 `late_arrival`이라는 사실만 표시한다. 지연 허용 시간이나 성과 정책은 추론하지 않는다. event 시각은 수신 가능 시각을 소급하지 않는다. 같은 source와 ID의 같은 raw hash는 논리 관측 한 건과 모든 receipt를 보존하며 `duplicate`를 표시한다. 다른 hash는 모든 raw와 hash를 보존하고 `conflict`를 표시한다. clock 오류나 conflict가 다른 후보와 겹치면 판단 순서를 만들지 않고 `unresolved`를 추가하며 후보 분류와 이유를 모두 남긴다. 원문 hash는 원문 UTF-8 bytes의 SHA-256이다.

`raw_versions`와 `receipts`는 전체 합성 fixture 기준이다. conflict/duplicate/provenance 그룹 분류는 checked 시각까지 available인 receipt만 사용하며, 미래 raw version은 보존하되 현재 conflict로 세지 않는다. `clock_invalid_receipts`는 각 receipt의 clock_invalid flag 전체(미래 포함)를 세고, 그룹 `clock_invalid` 분류는 available 또는 unknown 오류만 반영한다. `unknown_receipts`는 수신 시각 자체를 해석할 수 없는 receipt를 센다. 미래 receipt의 잘못된 event/read 시각은 receipt에 보존하지만 현재 available 집계를 오염시키지 않는다. `in_window`와 counts는 유효한 prospective 표본 수나 승인된 관측 수가 아니다.

## copyable synthetic fixture

다음 파일을 `fixture.json`으로 저장해 CLI에 사용할 수 있다.

```json
{
  "synthetic": true,
  "window_start_at": "2030-01-01T00:00:00Z",
  "window_end_at": "2030-01-02T00:00:00Z",
  "checked_at": "2030-01-02T00:00:00Z",
  "observations": [
    {"source_id":"demo","observation_id":"start","raw":"{\"v\":1}","received_at":"2030-01-01T00:00:00Z","event_at":"2030-01-01T00:00:00Z","read_started_at":"2029-12-31T23:59:59Z","read_finished_at":"2030-01-01T00:00:01Z"},
    {"source_id":"demo","observation_id":"end","raw":"{\"v\":2}","received_at":"2030-01-02T00:00:00Z","event_at":"2030-01-02T00:00:00Z","read_started_at":"2030-01-01T23:59:59Z","read_finished_at":"2030-01-02T00:00:01Z"},
    {"source_id":"demo","observation_id":"dup","raw":"same","received_at":"2029-12-31T23:00:00Z","event_at":"2030-01-01T00:00:00Z","read_started_at":"2029-12-31T22:59:59Z","read_finished_at":"2029-12-31T23:00:01Z"},
    {"source_id":"demo","observation_id":"dup","raw":"same","received_at":"2030-01-01T01:00:00Z","event_at":"2030-01-01T00:00:00Z","read_started_at":"2030-01-01T00:59:59Z","read_finished_at":"2030-01-01T01:00:01Z"},
    {"source_id":"demo","observation_id":"late","raw":"late","received_at":"2030-01-01T02:00:00Z","event_at":"2029-12-31T23:00:00Z","read_started_at":"2030-01-01T01:59:59Z","read_finished_at":"2030-01-01T02:00:01Z"}
  ],
  "required_boundaries": [{"boundary":"end","due_at":"2030-01-02T00:00:00Z"}],
  "truncation": {"total_count":5,"inspected_count":5}
}
```

이 fixture의 기대값은 다음과 같다. `start`는 `in_window`, `end`는 `out_of_window`, `dup`는 논리 관측 한 건·receipt 두 건·`duplicate`이며 최초 수신이 창 밖인 사실을 유지한다. `late`는 `in_window`와 `late_arrival`을 함께 가진다. end 경계는 `missing`, truncation은 `total=5`, `inspected=5`, `uninspected=0`, `truncated=false`이다. `counts.receipts`는 5, `counts.logical_observations`는 4이다.

## CLI

```bash
PYTHONPATH=backend .venv/bin/python -m jusik.research_future_observation_replay \
  --fixture fixture.json --output replay.json
```

출력 파일은 부모 디렉터리를 만들고 UTF-8 canonical key order JSON으로 쓴다. 입력과 출력 경로가 같거나 입력이 4 MiB를 넘으면 거부한다.
