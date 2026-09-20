# SEC batch action review form validator

- 상태: 완료 (operator batch form의 fail-closed validation); action ledger·NAV·성과 적용은
  미승격
- 기록 시각: 2026-09-20T04:50:00Z
- 범위: `SecActionReviewForm`과 `validate_sec_action_review_form()`을 추가해 priority
  dividend/split form의 accession·review key·원문 SHA·operator verification·revision/content
  hash·필수 날짜/금액/비율/share basis/PIT link를 한 번에 검증합니다. 이 validator는
  `ReviewManifest`를 만들거나 ledger를 적용하지 않습니다.

## 변경

- `research_sec_evidence --validate-review-form FORM --review-candidate-dir DIR
  --review-reference-queue QUEUE` CLI를 추가했습니다. 정본 queue의 symbol, source URL,
  raw SHA, required fields와 form을 exact-match하고 credential-free HTTPS URL 규칙도
  재사용합니다. source file이 누락되거나 SHA가 다르면 `ready=false`로 fail-closed합니다.
- form accession 집합이 정본 queue 전체와 정확히 일치해야 하며, 누락·예상 밖 accession은
  각각 `reference_missing_accessions`·`reference_unexpected_accessions`로 보고합니다.
- 전체 52개 event-near queue와 priority 8개 catalog를 구분합니다. priority form은
  `pure-action-review-priority.json`을 reference로 사용하고, loader가 이를 subset queue로
  변환합니다. 전체 queue를 reference로 잘못 연결해 정상 8개 form을 영구 차단하지 않도록
  CLI 경계를 명확히 했습니다.
- 기존 blank form과 호환되도록 `schema_version=1`, `status=operator_input_required`,
  `required_fields`를 허용합니다. 자동 ledger 적용 플래그는 항상 `false`입니다.

## 검증

- SEC evidence pytest: `13 passed`; Ruff·strict mypy·diff check 통과. 정본 queue identity
  변조와 CLI의 reference-queue 필수 gate 회귀도 확인했습니다.
- 통합 회귀 suite는 `126 passed, 2 warnings`를 통과했습니다. 전체 event-near source queue는
  `52/52` verified, missing `0`, SHA mismatch `0`, `ready=true`입니다.
- 실제 priority form 8개 검증: source SHA `8/8`, missing `0`, SHA mismatch `0`,
- reference missing/unexpected `0/0`, `ready=false`, exit `2`. 실패 이유는 operator
  facts·verification·revision/content hash 누락이며 원문 source gate 실패가 아닙니다.
- complete operator review fixture의 CLI 성공 경로도 검증해 `ready=true`, exit `0`을
  확인했습니다. 성공 시에도 `automatic_ledger_application=false`는 유지됩니다.
- 후속 SEC CLI 성공 경로 회귀 커밋 `27b1cba` 후 SEC evidence pytest는 `14 passed`입니다.

## 재개 조건

- 사용자가 form의 8개 row를 채운 뒤 같은 CLI가 `ready=true`, exit `0`을 반환해야 합니다.
- 이후에도 별도 `ReviewManifest` 생성·독립 review·coverage 확인 전에는 action ledger,
  NAV, CAGR/MDD/Sharpe 또는 PAPER/live로 승격하지 않습니다.
