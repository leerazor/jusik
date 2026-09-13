# 확장 universe 준비도와 사전등록

이 문서는 IVV·SGOV 확장 후보의 데이터 준비도와 실행 전 고정 protocol을 기록한다. 실제 데이터 수집·시뮬레이션 결과가 아니다.

## 후보와 근거

2026-09-13 UTC에 보존한 issuer/broker 공개 자료를 읽기 전용으로 확인했다. IVV는 S&P 500 광범위 주식 ETF(2000-05-15 설정, NYSE Arca, 분기 분배, 보수 0.03%), SGOV는 0–3개월 미국 국채 ETF(2020-05-26 설정, 현재 거래소 표기 NYSE, 월 분배, 보수 0.09%)다. 둘 다 USD unhedged다. issuer 30일 median quoted spread 0.01%는 2026-09-11 기준 참고값이지 실시간 호가나 과거 spread series가 아니다.

공식 자료는 [IVV](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf) (`ivv.html`, SHA-256 `0895841defe5b33299ce674de7d8144f003f2d8f857a656f46b002d5eb085715`)와 [SGOV](https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf) (`sgov.html`, SHA-256 `81312f286c6f5b010d3af075e833a76966267c20644ddec334e6c7b6ea9b73c5`)이며 retrieval은 모두 2026-09-13 UTC, source as-of는 2026-09-11이다. Broker 예시는 [daily price](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/dailyprice/dailyprice.py) (`kis-daily.txt`, SHA-256 `50715eb04f7b7556b7656ef82492e7295e83d5842dcb64a7f78ab61919e5fcf6`, declared Created 2025-06-26), [quote](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/price/price.py) (`kis-quote.txt`, SHA-256 `28e6654cf4fbd5369c23fe2ce738cdc540cc475a368d1307422457d12e16e942`, declared Created 2025-06-26), [websocket](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/asking_price/asking_price.py) (`kis-websocket.txt`, SHA-256 `50fa6d4722c3ba64f058ed34aeb7d7fe44017e902b20867053fa296267e1248c`, declared Created 2025-06-01)이다. 이 예시들은 3년 entitlement/coverage, 인증·지연시간, venue mapping(EXCD/tr_key)을 증명하지 않는다.

## 고정 A/B protocol

A는 현재 registry 16종목+현금, B는 여기에 IVV·SGOV만 추가한다. 양쪽 SOXL/TQQQ 목표는 각 총 NAV 10%(합계 20%)이며 가격 변동으로 실제 비중은 달라질 수 있다. A는 기존 비레버리지 14종목 각 5%와 KRW 현금 10%, B는 기존 14종목 합계 50%(균등), IVV 10%, SGOV 10%, KRW 현금 10%다. USD 현금은 별도 장부로 두며 현금 수익률은 보수적으로 0으로 가정하고 실제 금리로 표현하지 않는다. 시작 자본 100,000,000 KRW, 추가 입출금 0, 추가 환헤지 없음이다.

월말 UTC 평가 후 각 시장의 다음 정규 세션 시가에 한 번 리밸런싱하고, 초기 배분도 첫 평가 후 다음 시가에 적용한다. 정수주 내림·미체결 잔여금 현금 유지를 양쪽에 동일 적용한다. 최초 매수·매도·재투자·환전은 비용과 회전율에 포함하며, 내부 미수금의 현금 대체·배당 수령은 거래 회전율에서 제외한다. 비용은 매수/매도 각각 10bp 수수료+10bp all-in 미끄러짐, 환전 10bp라는 연구 가정이며 이중 공제하지 않는다.

대상 history는 2023-09-12~2026-09-11(포함), warmup 최대 180일이다. 상장 전 목표 몫은 현금으로 두고, 첫 완전한 정규 세션 검증 뒤 다음 월말부터 편입한다. 동일 UTC 일말의 마지막 정상 종가와 시각 이전 USDKRW를 사용하며 FX staleness는 정상 영업일 24시간·검증된 휴일/주말 96시간까지 허용한다. 원주가·실제 split 수량·분배금 권리/현금 장부를 사용하고, 배당락 보유수량으로 미수배당을 인식해 지급일 현금으로 대체한다. split·세금·원천징수 근거가 없으면 중단하며 수정주가에 분배/분할을 중복 적용하지 않는다.

`net return = NAV_end / 100,000,000 - 1`, `H_t = max(100,000,000, NAV_0, ..., NAV_t)`, `DD_t = 1 - NAV_t / H_t`, `MDD = max DD_t`다. 회복은 underwater 시작 후 같은 고점 이상이 된 첫 UTC 평가까지의 달력시간으로 정의하고, 미회복은 right-censored와 경과시간을 함께 기록한다. 회전율은 `sum(abs(executed KRW notional)) / mean(daily total NAV)`로 기간 누적·연환산(관측일수/365.25)을 각각 보고하며 FX turnover는 별도다.

## 현재 registry와 gate

고정 심볼/vendor/exchange는 `005930/005930.KS/KSC`, `000660/000660.KS/KSC`, `487230/487230.KS/KSC`, `487240/487240.KS/KSC`, `0173Y0/0173Y0.KS/KSC`, `0190C0/0190C0.KS/KSC`, `SOXL/SOXL/PCX`, `NVDA/NVDA/NMS`, `GOOGL/GOOGL/NMS`, `COHR/COHR/NYQ`, `TQQQ/TQQQ/NGM`, `MSFT/MSFT/NMS`, `ARM/ARM/NMS`, `AMD/AMD/NMS`, `GEV/GEV/NYQ`, `VRT/VRT/NYQ`다. 후보 mapping은 `IVV/IVV/PCX`, `SGOV/SGOV/NYQ`로 잠정 기록하며 broker 확인 전 미검증이다. registry/production은 변경하지 않는다.

현재 3년 history·FX·분배/분할·세금·venue mapping gate는 모두 미통과이고 simulation은 0회다. 공개 broker 자료의 daily endpoint, websocket top-of-book, IPO primary 검증, 거래소 캘린더·누락/중복/비유한 값, FX timestamp/휴일, 분배금 지급일과 세금을 후속 수집해야 한다. 기존 `OfflineResearchSnapshot`은 split parser 중심이며 분배금 미수·지급 장부가 없어 total return 준비 완료가 아니다. 실시간 stream 준비도는 historical daily 비교와 별도다. 하나라도 부족하면 비교를 실행하지 않고 gaps를 보존한다.

고정 원문과 hash 목록은 audit `sources.json`, 실행 설계는 audit `protocol.md`에 보존한다. 결과가 음수여도 retuning·winner selection·PAPER/production 반영을 하지 않는다.

## 구현 검증 기록

2026-09-13 UTC, isolated `backend/.venv` (Python 3.13.15)에서 다음 검사를 실행했다.

- `backend/.venv/bin/python -m pytest tests/test_development_runner.py tests/test_development_runner_planning.py -q`: 58 passed (11.69s)
- `backend/.venv/bin/ruff check jusik/development_runner.py tests/test_development_runner.py tests/test_development_runner_planning.py`: passed
- `backend/.venv/bin/python -m mypy --strict --follow-imports=silent jusik/development_runner.py tests/test_development_runner_planning.py`: passed
