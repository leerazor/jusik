# 등록 종목 비교 규칙 고정

- 상태: 설계 완료, 실제 실험 미실행.
- 기록 시각: 2026-10-03T12:56:19.313947+00:00
- 작업 slug: `selected-comparison-protocol-20261003`
- 기준/통합: `8e0038c` / `64391c8`.
- [규약](../research/approved-universe-comparison-protocol-v1.md)에 등록16/revision1·총1억원·후보equal/none과inverse_volatility/none·4주/2%p·원화NAV·레버리지20%·MDD20%·비용 및 미래 구간 동결 조건을 명시했다.
- 기존 equal은 추세 필터가 있어 순수 보유 기준선으로 대체할 수 없었다. 별도 회계 기준선 구현을 다음 단위로 선택했다. 이미 본 과거를 OOS라고 부르지 않으며 실제 설정·자료·기간 동결 전 실행하지 않는다.
- explore와 독립 plan 근거 반영, plan 중앙 routing pre/post PASS. 문서 diff 검사 PASS. 코드/API/UI/운영 변경이 없어 코드 검사는 없음.
- 요구수익률 미확정이면 투자 적격은 미판정. cap-control도 과거 비중 초과 기록을 삭제하지 않는다. 자동 승자·주문·승격·remote push 없음.
- 재개: [단순 보유 회계 인계](../handoffs/2026-10-03-approved-buy-hold-reference-20261003.md)의 검토·통합 상태를 확인하고 회계 기준선과 동일 조건 후보 입력을 연결한다.
- workflow 판단: 도움 됨 — 기존 추세 전략을 순수 보유로 오인하는 비교를 방지.
- 근거: 엔진 진입점 확인과 후보2개로 범위 고정, 시간/비용 절감 미측정.
- 다음 조정: 유지 — 128개 과거 grid 재실행 없이 최소 기준선부터 검증.
