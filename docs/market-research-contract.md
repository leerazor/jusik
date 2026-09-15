# 시장 연구 자료·결과 계약

이 문서는 R0-02의 시장 연구 API 계약을 정의합니다. 연구 결과는 한국과 미국을 별도 실행하며, 자료 등급(`strict` 또는 `approximate`)과 `simulated` 여부를 보존합니다. 이 계약은 기존 snapshot hash, `data_contract_hash`, 정책 hash, 전략 계산과 저장된 금융 수치를 변경하지 않습니다.

## 공개 경계와 private audit

공개 API는 `/api/research/market/status`, `/api/research/market/runs`, `/api/research/market/runs/{id}`를 사용합니다. 새 `provenance` metadata에는 서버의 절대 경로, 환경 파일 경로, 원시 응답 본문, 인증정보를 넣지 않습니다. 기존 `/api/research/market/artifacts/{artifact_id}` endpoint는 현재 라우터 동작에 따라 저장된 artifact bytes를 별도로 반환하며, 이 작업은 기존 route를 제거·변경하거나 새로운 접근 제어 보장을 추가하지 않습니다. 원시 source artifact와 큰 입력 파일은 private audit 디렉터리에 보존하고, 결과에는 기존 hash와 아래의 source identity만 전달합니다.

`MarketResearchResult.provenance`는 새 실행에서 snapshot의 실제 행과 artifact에서 도출한 선택적 provenance입니다. legacy 저장 결과처럼 필드가 없으면 `null` 또는 확인 불가로 해석합니다. 행이나 artifact가 비어 있을 때 source를 추정하지 않습니다.

| 필드 | 타입·단위 | 기본값 | 자료가 없거나 legacy인 경우 |
| --- | --- | --- | --- |
| `provenance` | `object \| null` | `null` | unknown |
| `universe_sources` | source identity 문자열 배열 | `null` | membership 행이 없으면 unknown |
| `bar_sources` | source identity 문자열 배열 | `null` | bar 행이 없으면 unknown |
| `fx_sources` | source identity 문자열 배열 | `null` | FX 행이 없으면 unknown 또는 해당 없음 판단은 소비자가 시장 계약으로 해석 |
| `artifact_sources` | source identity 문자열 배열 | `null` | source artifact가 없으면 unknown |
| `normalization_version` | 비어 있지 않고 40자 이하인 문자열 | `null` | normalized membership/bar 행이 없으면 unknown |
| `captured_at` | timezone offset을 포함한 ISO-8601 timestamp (UTC로 직렬화) | `null` | snapshot 자료와 artifact가 모두 없으면 unknown |

source identity는 `fixture`, `krx`, `massive`, `yahoo`, `alpha_vantage`, `fred`, `approximate_file` 중 하나입니다. 배열은 중복을 제거하고 정렬합니다. `provenance`는 결과의 설명 필드이며 snapshot hash 계산 대상이 아니므로, 이 필드를 추가해 기존 input/data contract hash가 달라지지 않습니다.

## 시간 의미

모든 timestamp는 UTC offset을 포함해야 하며, 날짜만 있는 `session`·`start_date`·`end_date`는 거래소 현지 거래일입니다.

| 시각 | 의미 | 결과 사용 규칙 |
| --- | --- | --- |
| `available_at` | 해당 membership·bar·FX 관측을 연구 계산에 사용할 수 있게 된 시각 | point-in-time cutoff와 비교하며 미래 관측을 사용하지 않음 |
| snapshot `captured_at` 및 provenance `captured_at` | snapshot 또는 source artifact를 수집·고정한 시각 | 자료를 읽은 시각이며 관측의 공개 시각을 대신하지 않음 |
| run `created_at`·`updated_at` | 연구 실행 레코드의 생성·갱신 시각 | 실행 이력용; 시장 관측 시각으로 사용하지 않음 |
| trade `signal_session`·`fill_session` | 신호가 확인된 거래일과 다음 체결 거래일 | strategy가 정한 다음 거래일 시가만 체결로 기록 |

`captured_at`이 있다고 해서 그 시각에 자료가 시장에서 이용 가능했다는 뜻은 아닙니다. 계산 가능성은 각 행의 `available_at`과 거래소 cutoff로 판정합니다. 실행 시각이나 run ID는 결과 수치의 입력이 아닙니다.

## 기간과 coverage

`request.start_date`·`request.end_date`는 평가 기간입니다. snapshot의 warmup과 원시 자료의 사전 기간은 결과 평가 기간과 구분합니다. `equity`와 `trades`의 `session`은 평가 기간 안에 있어야 하며, warmup은 신호 계산에만 사용합니다.

`metrics.coverage_sessions`는 실제 평가에 사용된 거래 세션 수입니다. `metrics.expected_candidate_bars`, `usable_candidate_bars`, `excluded_nonheld_bars`, `missing_held_bars`는 후보·보유 bar coverage를 설명하는 계산 지표입니다. 원시 snapshot 행 수(universe, bars, fx)와 서로 대체할 수 없으며, 원시 행 수는 private audit 또는 source 상태에서 보존합니다. 결측·부분 자료·기업행동 제한은 `limitations`와 `missing_ranges`에 남기고 유리한 기간으로 바꾸지 않습니다.

## 실행 상태와 오류

| run 상태 | `result` | `error` | 의미 |
| --- | --- | --- | --- |
| `queued`, `running` | `null` | 보통 `null` | 아직 결과를 만들지 않음 |
| `completed` | 존재 | `null` | 결과의 `status`·`completeness`·등급을 함께 확인 |
| `insufficient` | 존재 가능 | `null` 또는 설명 | 필수 자료·coverage가 부족해 경제 수치를 만들지 않음 |
| `failed` | `null` | 안전한 사용자용 설명 | 예외 또는 저장 실패; 원시 예외와 자격증명은 노출하지 않음 |

결과 `status`는 `ready`, `insufficient`, `approximate`이고 `completeness`는 `complete`, `incomplete`, `approximate`입니다. strict 결과의 평가 gate는 `completed` + `ready` + `complete`, approximate 결과의 gate는 `completed` + `approximate` + `approximate`입니다. `research_grade`는 request·readiness·result에서 같아야 하며, `simulated`는 자료의 실행 성격을 별도로 나타냅니다.

`status=insufficient`인 결과는 `metrics`, `trades`, `equity`가 비어 있을 수 있으며 이를 0 수익이나 성공으로 해석하지 않습니다. `status=approximate`는 무료 근사 자료의 한계를 뜻하고 strict PIT 검증 또는 PAPER·실거래 승인으로 승격되지 않습니다.

## 호환성

새 provenance는 optional nullable 필드입니다. 기존 저장 결과와 provenance가 없는 fixture는 계속 파싱되고 unknown으로 표시합니다. 프런트엔드 Zod schema도 누락 또는 `null`을 허용하지만, 값이 존재하면 source identity·timestamp·normalization 형식을 검증합니다. 기존 `request`, `metrics`, `trades`, `equity`, grade gate와 모든 Decimal 문자열의 의미는 유지합니다.
