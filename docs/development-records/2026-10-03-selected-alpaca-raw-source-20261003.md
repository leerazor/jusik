# 등록 미국10종목 원주가 확보

- 상태: 원천 준비·독립 검토 완료. 연구 인수/수익성 미평가.
- 기록 2026-10-03T13:52:56.880594+00:00; 작업 `selected-alpaca-raw-source-20261003`; 기준main de9153d.
- 이전 Alpaca22종목과 겹침0을 확인한 뒤 등록 revision1의 US10만 신규 조회했다. scope SHA `b1c03d1bfd986c2423f7478f27036de930800145837e8335fe590e5138646e44`에 요청·registry·일회성 collector·공식 문서 해시를 호출 전에 고정했다.
- [Alpaca 공식 규격](https://docs.alpaca.markets/us/reference/stockbars)의 `adjustment=raw` 무조정 의미와 `asof=-` ticker연결 제외를 명시했다. SIP/1Day/USD,2023-07-01T00:00Z~2026-10-03T00:00Z,10000봉/페이지,최대2페이지,실패재시도0. 실제 조회는1페이지200/다음토큰없음,7931봉이다.
- 8종목각817봉, ARM766봉(2023-09-14부터),GEV629봉(2024-04-02부터). 현재 고정 exchange_calendars4.12 기준817세션과 비교해 내부·후행·예상밖 날짜0. ARM선행51/GEV선행188세션은 아직 공식 상장 근거와 연결하지 않아 원인을 추정하지 않았다. 새 공식 달력 전체 검증은 아니다.
- 기존Yahoo재구성가격과 절대0.01USD 및 상대0.5%를 모두 넘는 차이를 진단했다. 임계값은 수용기준이 아니다. NVDA2024-06-10고가만195.95대123.099998로 차이가 남았다. 시가/종가가 이 진단에 걸리지 않았다는 것은 완전일치 증명이 아니다. 원문 대체·자료혼합·수익률 계산은 하지 않았다.
- 독립 review PASS: 원문/파싱7931봉,요청/registry/hash,페이지종료,NY자정·OHLCV·중복,달력 및차이 재계산 일치. 코드 변경 없는 한정 자료 작업으로 앱테스트 재실행 없음.
- 비공개 audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-alpaca-raw-source/`; manifestSHA `cd306b678328db89df618e0f34bf3eba72a3351ad1b8ecb42aa33cf1f55d357f`. 동결시 review_pending은 별도 independent-review.txt/review-completion.json으로 해소했다. 기존 manifest 불변.
- 원주가 원문·요청 결속은 확보했으나 security identity,일부고가충돌,분할·배당·FX·비용 계약 인수는 별도다. 이 준비를 수익성 검증이나 전체 가격 적격으로 표시하지 않는다.
- API키/인증헤더 저장·출력0,결제/주문/DB/서비스/PAPER/live/remote push 변경0. 등록16/rev1,runner inactive/governancefalse 유지.
- 다음은 NVDA해당일 고가의 별도 원천 판정 및 등록 종목 공식배당 보완이다. 같은 원주가 요청은 재실행하지 않는다. 이미 확보한 시가/종가 활용 여부는 실제 함수의 소비 필드와 별도 인수계약으로 정하며, 고가충돌을 숨기거나 임의허용치로 통과시키지 않는다.
- workflow 판단: 도움 됨 — 기존 실패 원천 재조회 없이1회7931봉 확보 및 독립검증. 시간/비용 절감 미측정; 다음 조정은 원천/소비필드별 남은 결손에 집중.
