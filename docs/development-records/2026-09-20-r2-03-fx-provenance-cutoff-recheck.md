# R2-03 FX provenance cutoff 재검증

- 기록 시각: 2026-09-20T03:00:00Z
- 입력 DB: `/home/kwl/.local/share/jusik/research-external.db`를 resolver의 read-only URI로 열었습니다.
- `FxProvenanceResolver`의 기존 정책과 cutoff를 변경하지 않았습니다.

## 결과

| cutoff (UTC) | state | reason | selected observation | age | candidates |
| --- | --- | --- | --- | ---: | ---: |
| 2025-09-11 23:59 | unavailable | `no_candidate` | — | — | 915 |
| 2025-10-13 23:59 | unavailable | `no_candidate` | — | — | 915 |
| 2025-11-11 23:59 | unavailable | `no_candidate` | — | — | 915 |
| 2026-04-03 23:59 | unavailable | `no_candidate` | — | — | 915 |
| 2026-09-11 23:59 | resolved | — | 2026-09-09 | 2 | 915 |

## 판정

- DB 행 수 자체는 충분해 보여도 역사 cutoff 이전의 `available_at`·archive 조건을 통과하지 못하면
  resolver는 fail-closed로 `no_candidate`를 반환합니다.
- 따라서 R2-03의 historical PIT FX와 canonical NAV application은 아직 증명되지 않았으며,
  결측을 0·carry-forward로 바꾸거나 현재 관측을 과거로 소급하지 않습니다.
