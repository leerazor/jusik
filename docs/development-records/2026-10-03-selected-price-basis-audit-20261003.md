# 등록 종목 원주가 기준 대사

- 상태: 원천·산술 대사 및 독립 검토 완료, 실제 연구 입력 인수는 미완료.
- 기록: 2026-10-03T13:48:49.526459+00:00; 작업 `selected-price-basis-audit-20261003`; 기준 main5b3cab0.
- 기존 research-universe DB를 읽기 전용 SQLite online backup으로 고정했다. KR6종목3010봉의 OHLCV는 보존 kis_raw와 십진수로 모두 같다. [한국투자증권 공식 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py)의 FID_ORG_ADJ_PRC=1 원주가 의미와 현 collector adjusted=False 요청을 대조했다. 당시 HTTP 요청 영수증까지 입증한 것은 아니다.
- NVDA2024-06-07 quote.close120.888을10배하여1208.88로 복원하고6/10부터factor1인 산술을 확인했다. quote가 분할 조정 가격이면 정상적인 원주가 복원이며, 이를 이중 분할 오류로 단정하지 않는다. 원주가와 실제 분할 수량 처리를 함께 적용하는 회계는 정상이다. Yahoo quote의 전반적 의미는 아직 미확인이다.
- 기존 Alpaca22근거는 등록US10과 겹침0. 기존자료 반복 조회 대신 새 등록범위 raw자료 준비로 진행했다.
- 검증: 고정7snapshot/원문 해시·KR3010행·NVDA3일 대사, 독립 reviewer PASS. 앱 코드·DB·서비스·주문·성과 변경0. 별도 pytest는 코드변경이 없어 미수행.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-price-basis/`; manifestSHA `3757e48e9aeaa607fdfed36272cf7b901c63f37464c3ca8a5f354a2ab462219c`. pinned 원문/정규화 및 probe 결과 보존, 독립 검토 파일 참조.
- 다음: 새 등록US10 Alpaca raw자료의 요청·분할·거래일·기존 가격 차이를 검증한다. Yahoo429 조회 반복, 코드label만으로 가격 적격 승격 금지.
- workflow 판단: 도움 됨 — 기존cache와3010행 비교로 추측한 오류를 교정했다. 시간/비용 절감은 미측정; 다음 조정은 실패조회 반복 없이 실제 대체원천 확보.
