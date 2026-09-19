# R2-03 환율·통화 경계 재검증

- 상태: 기술 계약 재검증 완료; 경제 평가는 `not-evaluated`, R2 전체는 미완료.
- 검증: accounting evidence, FX provenance, FX signal 테스트 46개 통과.
- 확인: USD/KRW as-of cutoff, exact/older/future observation 선택, stale·missing 오류,
  Decimal 기반 원화 반올림 경계를 독립 fixture로 확인했습니다.
- 한계: complete historical FX source coverage와 실제 거래 timestamp/비용·세금 근거가
  없어 경제 성과 계산을 승격하지 않습니다.
- 안전: 실제 주문·PAPER/live·운영 DB·원격 push 없음.
