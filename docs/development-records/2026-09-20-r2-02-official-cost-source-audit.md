# R2-02 official cost source audit

- 상태: 부분 근거 확보·기술/경제 완료 아님
- 기록 시각: 2026-09-20T06:40:00Z

## 공식 source

- 국가법령정보센터, `증권거래세법 시행규칙` [시행 2026. 3. 20.]:
  https://www.law.go.kr/LSW/lsRvsDocListP.do?chrClsCd=010202&lsId=008301&lsRvsGubun=all
  — 유가증권시장 증권거래세 `5/10,000`, 코스닥·K-OTC `20/10,000`을 명시합니다.
- U.S. SEC, `Section 31 Transaction Fee Rate Advisory for Fiscal Year 2026`:
  https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
  — 2026-04-04부터 covered sales 기준 `$20.60 / $1,000,000`을 명시합니다.
- U.S. SEC, `Section 31 Transaction Fees: Basic Information for Firms`:
  https://www.sec.gov/rules-regulations/fee-rate-advisories/section-31-transaction-fees-basic-information-firms
  — Section 31 의무는 SRO에 있고 broker가 고객에게 부과하는 비용은 broker/SRO 계약에
  따라 별도임을 명시합니다.

## 결정

- 현재 `market=KR`만으로 KOSPI/KOSDAQ 세율을 선택할 수 없고, 미국 Section 31 rate를
  broker 고객 비용이나 `sell_tax_rate`로 직접 치환할 수 없습니다.
- 따라서 코드·frozen 결과·요율을 변경하지 않았습니다. R2-02는 여전히 미완료이며, 실제
  순수익·CAGR·MDD·PAPER 승격에 이 부분 근거를 사용하지 않습니다.
- 다음 조건은 broker/계좌 fee schedule, 상품·시장·유효기간, 체결/결제 시점, 한국 관련
  세목(농특세 포함 여부)을 결과 contract에 고정하는 것입니다.
