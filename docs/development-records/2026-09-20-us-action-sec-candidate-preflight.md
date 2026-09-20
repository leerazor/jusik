# US action SEC candidate preflight

- 기록 시각: 2026-09-20T03:22:00Z
- 목적: approximate collection에서 `observed_at=null`로 남은 기업행사의 보조 원문 후보를
  자동 수집하되, action ledger나 성과 계산에 적용하지 않습니다.

## 결과

- 대상: collection event 31개 심볼, SEC ticker map CIK match `31/31`
- 기간: 2025-01-01~2026-09-11 submissions `4,268`건
- 8-K/8-K/A: `607`건
- 심볼별 bounded primary-document 후보: `26`건
- 자동 text candidate: dividend `5`, merger `2`
- `submission-summary.json` SHA-256:
  `ffbf5711eb6a2105e0c240a390e11cb43a7230b59a9c8424ad42c84ec4a43995`
- `candidate-summary.json` SHA-256:
  `efe2f2668755095518c8b0454e9f4963b774d83e4c0dc559d74200d98656d054`

## 판정

SEC filing 후보의 자동 text match는 dividend amount, ex-date, split ratio, 권리수량 또는
Yahoo event와의 동일성을 증명하지 않습니다. 후보는 `operator_verified=true` ReviewManifest와
추출 사실·원문 locator·revision hash가 준비되기 전까지 보조 evidence로만 보존합니다. 관측시각을
Yahoo event에 전이하거나 기존 action DB를 수정하지 않았습니다. 따라서 US pilot은 여전히
`insufficient`이며 R1-04/05, R4-02~05, 경제 지표와 PAPER 승격은 차단 상태입니다.
