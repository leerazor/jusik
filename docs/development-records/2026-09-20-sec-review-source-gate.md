# SEC review queue 원문 source gate

- 상태: 기술 구현·검증 완료, action 사실 및 경제 적용 보류
- 구현: `verify_sec_review_queue_sources()`가 queue의 각 accession에 대해 bounded local
  HTML을 읽고 `raw_sha256`와 대조합니다. 원문 누락·크기 초과·심볼릭 링크·SHA 불일치는
  `ready=false`로 남깁니다. `build_sec_action_review_input()`도 manifest 생성 시 evidence
  파일 존재·크기·SHA를 재검증하며, 두 경로 모두 operator approval이나 ledger application을
  수행하지 않습니다.
- 실제 검증: `event-near-review-queue.json` 52개와 `event-near-candidates/`를 대조해
  `queue_items=52`, `verified_items=52`, `missing_accessions=[]`,
  `sha_mismatch_accessions=[]`, `ready=true`를 확인했습니다.
- CLI 검증: `python -m jusik.research_sec_evidence --verify-queue <queue> --candidate-dir
  <event-near-candidates>`가 동일한 JSON을 출력하고 exit `0`으로 종료했습니다. 누락·불일치
  입력은 exit `2`로 fail-closed 처리합니다.
- 회귀: SEC evidence/action 관련 pytest `32 passed`(경고 2건), Ruff, strict mypy,
  `git diff --check` 통과.
- 제한: source-ready는 원문 보존만 의미합니다. `unsupported_candidate` 및
  `automatic_ledger_application=false`를 유지하며, event/effective date·금액/비율·share
  basis·PIT link의 operator verification 전에는 원장·NAV·성과 계산에 적용하지 않습니다.
