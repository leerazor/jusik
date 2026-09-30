# 미국 워런트 분류 인계

- 작업 `us-warrant-classification-20260930`; [개발 기록](../development-records/2026-09-30-us-warrant-classification.md)과 [검증 결속](../../../../.local/share/jusik/portfolio-audit/20260930-us-warrant-classification/verification.json) 참조. main 병합 SHA는 감독자가 확정한다.
- 신규 collector 출력은 `approx-us-r1-event-timing-v4`; `Wt Exp` 뒤 8자리 날짜인 명칭을 워런트로 분류하고 v4 reader·완료 검증에서 재표시를 차단한다. 기존 v2/v3 자료·marker·계약 해시는 보존했다.
- focused pytest 54개와 Ruff·strict mypy·mandate/dispatch 검사 통과. 실제 시장 요청, 수집, 금융 실험, 주문 0회. 독립 review와 main 통합은 감독자 예정.
- v4 표본 재선정·miss·사건 125행의 관측 근거 및 비용/NAV 적격성은 미평가. 새 수집보다 먼저 기존 cache에 대한 v4 오프라인 선정 차이를 고정하고, 사건 근거는 별도 범위로 검토한다. 기술 완료를 투자 성과로 승격하지 않는다.
- workflow: 기확정 회귀와 고정 원문을 재사용했다. 좁은 계약 변경을 기존 자료 보존 검증과 함께 마쳤다. 다음 독립 작업은 관측 가능한 자료 결손을 줄일 때만 연다.
