# R1 action collection/review DB 감사

## 입력 identity

- collection DB: `/home/kwl/.local/share/jusik/portfolio-audit/20260910T074300Z-action-collection/discovery-replay-final.db`
- collection DB SHA-256: `838715af71cc1f16c1367779a7a010db1ab99a613cd6f605a7757c854a6594ae`
- review DB: `/home/kwl/.local/share/jusik/portfolio-audit/20260910T100314Z-dividend-accounting/review-eligibility-probe.db`
- review DB SHA-256: `873c644d8fff74c9dd3c34880e30d054a2811e480214abfb904a56df94139a06`

## 확인 결과

collection DB에는 128 attempts(127 success, 1 failure), 12 events, 14 revisions가 있다. 각 revision은 provider key, first-seen UTC, attempt ID, payload SHA와 raw payload를 보존한다.

review DB에는 공식 evidence 3개와 review 6개가 있다. 공식 matched 근거는 다음과 같다.

- NVDA split: 10:1, adjusted trading date 2024-06-10, NVIDIA FAQ PDF SHA `7f6b7651d7874784cd7666464431395e62a9570a139932183470094c4d51faf3`.
- TQQQ split: 2:1, adjusted trading date 2025-11-20, ProShares release SHA `896070b90d8c6d626f3b62a8204dc5735292b3ef298106b5cdf253647b0356c3`.
- NVDA dividend: USD 0.01, ex/record 2024-06-11, payment 2024-06-28, NVIDIA FAQ evidence SHA `7f6b7651d7874784cd7666464431395e62a9570a139932183470094c4d51faf3`.

추가 NVDA 2026 dividend review는 amount/payment는 matched지만 ex-date가 누락되어 `partial`이다. review 집계는 matched 4, partial 1, mismatched 1이며 mismatched는 synthetic wrong-amount fixture다.

## 판정과 다음 작업

이는 실제 provider receipt와 공식 evidence가 전혀 없다는 이전 가정을 정정하지만, 전체 action coverage나 모든 권리 경계를 충족하지 않는다. 따라서 R1-04/R1-05 checkbox, strict PIT, prospective validation, 경제 성과 acceptance는 변경하지 않는다. 다음 최소 작업은 이 고정 DB identity를 변경하지 않는 read-only canonical evidence 연결/preflight이며, partial·mismatch를 성공으로 숨기지 않아야 한다.
