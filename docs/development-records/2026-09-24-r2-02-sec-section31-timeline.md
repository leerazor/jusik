# 2026-09-24 R2-02 SEC Section 31 timeline

## 공식 원천

SEC의 [FY2025 Fee Rate Advisory](https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2)는 covered sales의 Section 31 rate를 2025-05-14부터 `$0.00 per million`으로 낮췄다고 명시한다. [FY2026 Advisory](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2)는 2026-04-04부터 `$20.60 per million`으로 적용한다고 명시한다.

따라서 canonical pilot 기간 `2025-09-11`~`2026-09-11`의 법정 SEC rate timeline은 다음과 같다.

| charge date | SEC Section 31 rate |
|---|---:|
| 2025-09-11 ~ 2026-04-03 | `$0.00 / $1,000,000` |
| 2026-04-04 ~ 2026-09-11 | `$20.60 / $1,000,000` = `0.00206%` |

SEC advisory는 SRO가 SEC에 납부할 covered-sale rate를 정한다. 국내 broker가 고객에게 전가하는 방식, 최소 청구액, 거래명세서 표시, 매도 체결일과 결제일 중 적용 기준은 별도 Kiwoom 계약/receipt로 검증해야 한다. 따라서 이를 기존 `sell_tax_rate`에 자동 주입하지 않았고 R2-02 checkbox와 경제 acceptance는 미승격한다.

## 후속 조건

Kiwoom 계좌·매체별 broker fee schedule과 실제 fill/settlement receipt를 SEC timeline에 결속한 뒤에만 비용 evaluator의 적용 시점을 결정한다. SEC rate 자체와 broker customer charge를 합산해 중복 계상하지 않는다.

