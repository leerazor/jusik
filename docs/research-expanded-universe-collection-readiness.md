# 확장 universe 실제 자료 수집과 gate 결과

이 문서는 `portfolio-expanded-universe-collection-gates-v1` 시도 `2ea67734308a40eda685c1b0839576c6`의 단일 bounded collection 결과다. 비교·simulation·sweep은 실행하지 않았고 결과에 따라 자료 준비도는 차단 상태다.

수집 요청은 네트워크 호출 전에 고정했다. 대상 기간은 `2023-09-12`~`2026-09-11`(포함), warmup은 최대 180일이다. 원래 baseline인 registry 16종목·KRW/USD cash를 보존하고, 확장 후보는 IVV와 SGOV로만 고정했다. 요청은 10개로 최대 40개, 요청당 timeout 30초·응답 20MiB, retry 0, pagination 0, fallback 0이다. 요청 정의와 응답 원문·UTC 시각·HTTP status·크기·SHA-256은 audit 산출물에 보존했다. 최신 mandate의 “불필요한 현금 대기 축소”와 “짧은 이력으로 비교가 막히는 신규 ETF 제외”는 정책 조건이며, 이번 수집은 기존에 동결된 IVV·SGOV 비교 후보의 자료 gate를 확인하는 별도 단계다. 투자기간은 아직 미정이다.

실제 응답은 다음과 같았다.

- [iShares IVV distribution download](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_distributions&dataType=fund)와 [SGOV distribution download](https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf/1467271812596.ajax?fileType=csv&fileName=SGOV_distributions&dataType=fund)는 HTTP 200과 `text/csv` MIME을 반환했지만 실제 본문은 issuer product HTML이었다. 그 HTML에 포함된 issuer distribution 표를 오프라인에서 해석해 IVV 12건, SGOV 36건을 추출했다. 각 행은 ex-date, record date, payable date, USD total distribution을 갖고, 기간 내 중복·양수 금액·`ex ≤ record ≤ payable`을 독립 검사했다. IVV 관측 범위는 earliest 2023-09-26~latest 2026-06-15, SGOV 관측 범위는 earliest 2023-10-02~latest 2026-09-01이다.
- IVV·SGOV pricing URL도 HTTP 200 HTML이었고 이번 pass에서 정규화·추출된 가격 관측은 0건이었다. 이 응답을 가격 history로 간주하지 않았으며, issuer history의 실제 제공 범위는 미확정이다.
- [Federal Reserve H.10 download](https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=csv&label=include&layout=seriescolumn&from=09/12/2023&to=09/11/2026)는 HTTP 200이지만 본문 크기 0이었다. point-in-time USDKRW 관측은 0건이다.
- [NYSE IVV](https://www.nyse.com/quote/etf/IVV)·[SGOV](https://www.nyse.com/quote/etf/SGOV) quote 페이지는 HTTP 200 HTML이었지만 이 pass에서 안정적인 listing-master 매핑을 증명하지 못했다. [NYSE hours/calendars](https://www.nyse.com/markets/hours-calendars) URL은 HTTP 302였고, 동결 조건에 따라 redirect를 따르지 않았다.
- [IRS nonresident alien](https://www.irs.gov/individuals/international-taxpayers/nonresident-aliens) 페이지와 [한미 조세조약 원문](https://www.irs.gov/pub/irs-trty/korea.pdf)은 수집했으며, IRS 페이지에서 “flat 30 percent (or lower treaty rate)” 문구를 확인했다. 투자자 거주지·계좌·조약 적용·broker withholding 구현은 고정되지 않아 세금 gate를 통과시키지 않았다.

| Gate | 상태 | 확인된 사실과 남은 gap |
| --- | --- | --- |
| Prices | 차단 | 후보 가격 관측 0건. 3년 일별 시장 가격·정규장 coverage 필요 |
| Dividends | 차단 | 후보 issuer 표 12/36건의 행 구조·날짜·양수 금액은 통과했으나 baseline 16종목 action 자료와 원천징수·settlement가 없음 |
| Splits | 차단 | distribution 표는 split stream이 아니며 no-split completeness 근거가 없음 |
| FX | 차단 | H.10 응답 빈 본문, USDKRW 시각·휴일·staleness 검증 불가 |
| Tax | 차단 | IRS 일반 규칙·조약 원문은 보존했지만 실제 계좌 조건과 분배별 withholding 미확정 |
| Calendar | 차단 | 이번 pass에서 full historical primary session/holiday grid 미검증 |
| Venue | 차단 | IVV PCX·SGOV NYQ broker mapping 미검증 |
| Coverage | 차단 | 후보 가격·FX가 없고 baseline 16종목의 primary coverage도 이 pass 범위 밖 |

따라서 기존 IVV·SGOV·cash 사전등록과 PAPER 10% 계약은 변경하지 않는다. 이 자료로 비교를 실행하거나 후보를 승격할 수 없다. 다음 자료 수집은 가격·FX·corporate action/split·세금·거래소 달력·broker venue를 각각 primary 원문으로 보강한 뒤, 동일 gate를 다시 통과시키는 별도 시도여야 한다.

재현 산출물은 task/attempt audit의 `collection-request.json`, `responses.ndjson`, `raw/`, `extracted-distributions.csv`, `extracted-distributions.json`, `validation.json`, `execution-provenance.json` 및 offline validator다. 초기 수집기 파서는 raw capture 후 HTML 표를 처리하는 단계에서 `AttributeError`가 발생했으며, raw 응답을 보존한 뒤 네트워크 재실행 없이 별도 offline validator로 추출을 완료했다. 네트워크 실행 당시 collector 소스 hash는 사전에 캡처하지 못했으므로 provenance에 null로 명시했다.
