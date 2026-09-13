# 연구 mandate

이 문서는 자동 연구 planner가 따라야 하는 현재 연구 범위의 요약이다. 정확한 값과 원문은 함께 추적하는 `research-mandate.json`을 기준으로 하며, 이 문서와 planner prompt의 요약이 충돌하면 JSON을 따른다.

- 초기 자본은 1억 원이다. 총 포트폴리오의 running peak mark-to-market NAV(초기 자본 포함) 대비 최대 낙폭 목표는 20%이며 중간 인출은 없다.
- 비교 universe는 기존 종목에 현금, 광범위 지수 ETF, 단기채 ETF를 추가한다. 이번 준비도 후보는 IVV·SGOV와 KRW/USD 현금이며, 이는 미래 universe를 영구 제한하는 선언이 아니다.
- 과거 자료 lookback은 3년이고 투자 horizon은 아직 정하지 않았다. 레버리지 배분 상한은 20%, turnover 선호는 낮음, signal detection은 real-time이다. live trading은 유보한다.
- PAPER 계약은 변경하지 않으며 10% drawdown 계약을 유지한다. 실제 주문, PAPER 설정 변경, 근거 없는 수익·history 완전성 주장은 금지한다.

## IVV·SGOV 준비도

2026-09-13 UTC에 보존한 issuer/broker 공개 자료를 읽기 전용으로 확인했다. IVV는 S&P 500 광범위 주식 ETF(2000-05-15 설정, NYSE Arca, 분기 분배, 보수 0.03%), SGOV는 0–3개월 미국 국채 ETF(2020-05-26 설정, issuer 페이지의 현재 거래소 표기는 NYSE, 월 분배, 보수 0.09%)다. 두 상품 모두 USD unhedged이므로 KRW 기준 비교에는 USDKRW 노출이 포함된다. issuer 30일 median quoted spread 0.01%는 2026-09-11 기준 한 시점의 참고값이지 실시간 호가나 과거 spread series가 아니다.

공개 broker 자료의 daily price 예시와 US realtime top-of-book websocket 예시는 보존했지만, 3년 history entitlement/coverage, venue key mapping(EXCD/tr_key), 인증·지연시간은 확인하지 않았다. 따라서 아직 history 수집·시뮬레이션·실시간 broker 호출을 하지 않는다. 현금은 KRW와 USD로 식별하며 bars/inception은 없고, 수익률·이자·환율 시계열·세금·분배금 처리는 별도 수집 전까지 확정하지 않는다. 기존 `OfflineResearchSnapshot`은 분할 parser 중심이고 분배금 미수·지급 장부를 구현하지 않으므로 dividend-adjusted total return을 준비 완료로 간주하지 않는다.

## 사전등록된 A/B 비교 설계

분석은 현재 registry 16종목+현금인 A와 여기에 IVV·SGOV를 더한 B의 한 쌍만 비교한다. 두 arm 모두 SOXL과 TQQQ를 총 NAV의 각 10%(합계 20%)로 목표 배분하고, A의 나머지 14종목은 각 5%와 KRW 현금 10%, B의 나머지는 14종목 합계 50%(균등), IVV 10%, SGOV 10%, KRW 현금 10%로 둔다. USD 현금은 별도 장부로 두고 이자를 주지 않으며 추가 환헤지는 없다. 시작 자본은 100,000,000 KRW, 추가 입출금은 0이다. 월말 UTC 평가 뒤 각 시장의 다음 정규장 시가에 한 번 정수주 내림으로 리밸런싱하고, 미체결 잔액은 현금으로 남긴다.

대상 기간은 2023-09-12~2026-09-11(포함), 기업행동 warmup은 최대 180일이다. 상장 전 배분은 현금으로 두고 상장 후 첫 완전한 정규 세션 검증 뒤 다음 월말부터 편입한다. 평가에는 같은 UTC 격자의 마지막 정상 종가와 시각 이전 USDKRW를 쓰며, FX staleness는 정상 영업일 24시간·검증된 휴일/주말 96시간까지만 허용한다. 배당락 보유수량으로 미수배당을 잡고 지급일에 현금으로 대체하며, 분할·세금·원천징수 근거가 없으면 중단한다.

고정 비용 가정은 매수·매도 각각 수수료 10bp와 미끄러짐 10bp, 환전 10bp다. 이는 실계좌 요율이나 과거 spread 측정이 아니다. `net return = NAV_end / 100,000,000 - 1`, `H_t = max(100,000,000, NAV_0, ..., NAV_t)`, `DD_t = 1 - NAV_t / H_t`, `MDD = max(DD_t)`를 사용한다. 회전율은 `sum(abs(executed KRW notional)) / mean(daily total NAV)`로 기간 누적·연환산을 각각 보고하고, FX turnover는 별도 계산한다. 회복하지 못한 underwater episode는 right-censored로 기록한다. 결과가 음수여도 retuning·winner selection·PAPER/production 반영을 하지 않는다.

현재 registry의 16개 고정 심볼과 vendor mapping은 `005930/005930.KS/KSC`, `000660/000660.KS/KSC`, `487230/487230.KS/KSC`, `487240/487240.KS/KSC`, `0173Y0/0173Y0.KS/KSC`, `0190C0/0190C0.KS/KSC`, `SOXL/SOXL/PCX`, `NVDA/NVDA/NMS`, `GOOGL/GOOGL/NMS`, `COHR/COHR/NYQ`, `TQQQ/TQQQ/NGM`, `MSFT/MSFT/NMS`, `ARM/ARM/NMS`, `AMD/AMD/NMS`, `GEV/GEV/NYQ`, `VRT/VRT/NYQ`이다. 이 registry와 production 설정은 변경하지 않는다. ARM·GEV·한국 ETF의 신규 상장일은 primary source 재검증 전까지 gate 미통과다.

실행 gate는 심볼·venue mapping, 실제 3년 coverage, IPO 예외, 가격·분배·분할·세금, USDKRW 시각·휴일, 비용, 원본 hash의 독립 검증이다. 현재 history/FX/action 수집은 모두 미완료이고 simulation은 0회이므로 비교를 실행하지 않는다. 실시간 신호 준비도도 broker market-data only 스트림의 거래소·수신 UTC·bid/ask·stale/gap·재접속을 별도 확인해야 하며, historical daily 비교가 이를 증명하지 않는다.

후속 수집은 source URL·retrieval UTC·응답 hash를 고정하고, 각 상품의 상장 이후 일별 OHLCV·분배/분할·거래소 캘린더·USDKRW 시각 정렬·누락/중복/비유한 값과 coverage를 검증한다. 3년 완전성이 입증되기 전에는 성과 비교나 winner selection을 하지 않는다. 본 비교의 고정 protocol은 audit의 `protocol.md`에 보존되어 있다.

근거 원문과 hash 목록은 audit의 `sources.json`에 보존한다. 공식 issuer 페이지는 [IVV](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf) (`ivv.html`, SHA-256 `0895841defe5b33299ce674de7d8144f003f2d8f857a656f46b002d5eb085715`)와 [SGOV](https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf) (`sgov.html`, SHA-256 `81312f286c6f5b010d3af075e833a76966267c20644ddec334e6c7b6ea9b73c5`)이며 둘 다 2026-09-13 UTC에 retrieval했다(자료 기준일 2026-09-11). Broker 예시는 [daily price](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/dailyprice/dailyprice.py) (`kis-daily.txt`, SHA-256 `50715eb04f7b7556b7656ef82492e7295e83d5842dcb64a7f78ab61919e5fcf6`), [quote](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/price/price.py) (`kis-quote.txt`, SHA-256 `28e6654cf4fbd5369c23fe2ce738cdc540cc475a368d1307422457d12e16e942`), [websocket](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/asking_price/asking_price.py) (`kis-websocket.txt`, SHA-256 `50fa6d4722c3ba64f058ed34aeb7d7fe44017e902b20867053fa296267e1248c`)이다. 이 보고서는 준비도 기록이며 실제 데이터 수집 결과가 아니다.
