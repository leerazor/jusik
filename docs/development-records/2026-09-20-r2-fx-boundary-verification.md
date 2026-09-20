# R2-03 환율·통화 경계 재검증

- 상태: 기술 계약 재검증 완료; 경제 평가는 `not-evaluated`, R2 전체는 미완료.
- 검증: accounting evidence, FX provenance, FX signal 테스트 46개 통과.
- 확인: USD/KRW as-of cutoff, exact/older/future observation 선택, stale·missing 오류,
  Decimal 기반 원화 반올림 경계를 독립 fixture로 확인했습니다.
- 한계: complete historical FX source coverage와 실제 거래 timestamp/비용·세금 근거가
  없어 경제 성과 계산을 승격하지 않습니다.
- 추가 대사: ALFRED 주간 vintage의 251개 관측을 관측일별 first-seen upper bound와
  비교했습니다. 같은 날짜 또는 이전 vintage로 증명된 관측은 `0/251`이고, first-seen
  lag는 `7~11일`이었습니다. 이 자료는 historical source evidence이지만 US session
  평가 시각 이전 availability를 증명하지 않으므로 FX/NAV 입력으로 연결하지 않습니다.
- 안전: 실제 주문·PAPER/live·운영 DB·원격 push 없음.
