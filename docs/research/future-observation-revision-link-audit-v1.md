# 합성 future-observation revision link 감사 v1

이 연구 산출물은 합성 receipt fixture와 별도 `revision_links` 문서의 연결 선언을 읽기 전용으로 감사한다. 원문, receipt 순서, replay 결과와 모든 link 선언을 결과에 보존한다. 원문 identity는 `(source_id, observation_id, raw의 실제 UTF-8 SHA-256)` 세 값으로 정한다. 같은 원문 receipt가 반복되어도 새 version이나 모호한 부모가 되지 않는다.

각 link는 child identity와 `parent_sha256`, timezone-aware `effective_at`을 선언한다. 링크가 없는 identity는 root로 허용한다. 부모 부재, 서로 다른 부모 선언, source 또는 observation을 넘는 후보, self-link, cycle의 모든 구성원, 중복 선언, 실제 raw와의 hash 불일치, 잘못된 시간을 진단 기록으로 남긴다. malformed hash와 시간도 구조적으로 읽을 수 있으면 원문 선언을 버리지 않는다. 시간의 순서·권위·availability 정책은 이 감사의 범위가 아니며 `selection_policy`와 `temporal_policy`는 항상 `unresolved`로 남긴다.

입력 문서는 `synthetic`을 반드시 JSON boolean `true`로 포함해야 한다. fixture는 replay의 `observations`를 포함하고, link 문서는 아래 형태를 따른다.

```json
{
  "synthetic": true,
  "revision_links": [
    {
      "source_id": "source-a",
      "observation_id": "observation-1",
      "raw_sha256": "<child raw UTF-8 SHA-256>",
      "parent_sha256": "<parent raw UTF-8 SHA-256>",
      "effective_at": "2030-01-01T00:00:00Z"
    }
  ]
}
```

결과의 `synthetic`은 항상 `true`이고 `registered`, `accepted_nav`, `evaluation_inputs_complete` 안전 플래그는 항상 `false`이다. `selection_policy`와 `temporal_policy`는 모두 `unresolved`로 출력한다. 권위 revision을 선택하거나 availability를 변경하지 않는다. 이 모듈은 archive, database, API, collector, runtime, order execution을 호출하지 않는다.

CLI는 다음처럼 실행한다.

```bash
python -m jusik.research_future_observation_revision_audit \
  --fixture fixture.json --revision-links revision-links.json --output audit.json
```

두 입력 각각은 4 MiB 이하이고 receipt와 link는 각각 10,000개 이하이어야 한다. 출력은 UTF-8, 정렬된 JSON으로 고정하며 기존 출력 파일이나 입력과 inode를 공유하는 경로에는 쓰지 않는다.
