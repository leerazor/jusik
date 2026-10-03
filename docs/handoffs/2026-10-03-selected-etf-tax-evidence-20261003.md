# 등록 ETF 증거 보완 후 계속

- 2026-10-03T12:10:15Z, `/home/kwl/projects/jusik`, 기준main c397eba. 사용자 단계별 지속 진행 승인; 완료 후 다음 작업을 이어간다.
- [기록](../development-records/2026-10-03-selected-etf-tax-evidence-20261003.md): KODEX3 상품 신원·현재 표시 세금/보수 확보, 관측 분배11건 독립 검토·실제 검토 DB append 완료. eligible24/111, coverage9b02afa9... . 원장·수익성 검증 아님.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-etf-tax-evidence/`, final-manifest SHA d6c630b2... . 5+3+3 실제 반영 증거와 source bytes 재사용. SQLite 사본은 WAL 포함 backup 필수.
- RISE0190C0는 상품 신원/국내주식만 확보. viewer14945/14946 및 연결 PDF가 홈페이지 HTML 반환; 동일 재조회 금지. 새 공식 문서 경로가 재개 조건.
- 배당금과 과세 대상 분배금은 다를 수 있다. 과세기준가·역사적 비용 유효기간·개별계좌 비용은 미확인. 표시 보수를 가격에서 이중 차감하지 않는다.
- 다음 작업: 삼성전자005930/SK하이닉스000660의 현재 DB exact revision을 추출하고 사건별 공식 일정을 연결. annual 합계를 quarterly 사건으로 추정하거나 배당락일을 단순 계산해 확정하지 않는다.
- 기존 source 조사 agent는 read-only, supervisor 단일 DB writer. 코드 변경 필요 시 기존 free 관리형 checkout과 중앙 routing/독립 review 절차 재사용.
- 등록16/revision1, 1억원·레버리지20%·MDD20% 유지. 자동매매·실주문·승격·Pages·remote push 없음. 루트 HANDOFF.md 보존. heartbeat 기존30분 유지.
