# R6 KRX 자료 경로 재검증

- 상태: 기술 계약 재검증 완료; 한국 경제 성과는 별도 실행 전까지 `not-evaluated`.
- 검증: market data collector 및 performance readiness 테스트 167개 통과.
- 확인: KRX zero-OHLC/volume 0 행은 membership만 보존하고 bar를 만들지 않으며,
  malformed OHLC는 거부합니다. KRX 인증·cache·prepared path와 US provider 경로가
  분리되고 market/readiness 오류가 독립 상태로 남습니다.
- 한계: 이 검증은 실제 한국 수익률·benchmark를 만들지 않으며 미국 결과와 혼합하지 않습니다.
- 안전: 실제 주문·PAPER/live·원격 push 없음.
