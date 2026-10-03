# 등록 종목 비용 원천 보완 후 계속

- 2026-10-03T11:38:22Z, `/home/kwl/projects/jusik`, 기준main `8adc605`. 단계별 지속 진행 승인. 자동매매·실주문·PAPER/live·Pages·remote push 제외.
- 합성 NAV16거래/89평가시점 독립 대사 완료: [이전 인계](2026-10-03-nav-cost-fx-oracle-20261003.md). 실제 비용·세금·전체 배당·PIT·수익성 완료는 아니다.
- [이번 기록](../development-records/2026-10-03-selected-cost-contract-20261003.md): 기존 비용 모델의 상품/기간별 적용 결손 확인, 신규 범용 계약 구현 대신 공식 BanKIS 설명서1건과 등록16 비용 결손표 확보. 독립 review PASS. application 변경 없음.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-cost-contract/`; manifest `fd71720e...`. 원문55,917bytes SHA4e601deb...; 일반주식과ETF 수수료 행 다름. 코스피 세금 합계도 기존 동결 profile과 다름. 원문 심사일/개정일은 요율 시행일이 아니며 과거3년·실제계좌에 적용하지 않았다. 원문 재수집 불필요.
- readiness는16/revision1·국내6 source fact 후보연결·해외10 미연결·ready0·rates_applied=false. 결손은 상품/market 검증 신원, 과거유효기간, 계좌/채널, 최소액·반올림·체결/결제 기준, ETF과세기준가, 해외고객비용/FX 등. 신청자 개인정보·체결명세 없다는 이유로 모든 연구를 막지 말고 가정 시나리오와 실제 비용 주장을 구분한다.
- **다음 단일 작업:** 등록 국내ETF4개(487230/487240/0173Y0/0190C0)의 기존 공식 issuer 근거부터 찾아 비용·과세유형 및 종목코드 연결을 보완한다. 전체 주식 매도세를 일괄 적용하지 않는다. 자료 접근이 막히면 실패cache를 보존하고 준비된 다른 종목의 공식배당/분할 근거로 전환한다.
- 원천이 준비되면 같은 종목·기간·통화·비용의 단순보유/최대3 저회전 후보를 사전등록한다. 성과는 아직 미실행. 이미 본 과거를 untouched OOS라 하지 않는다.
- 실제 API8001 확인: 등록16/revision1; runner/service/timer/optimizer inactive. 기존 source13/111 배당 적격 유지. 워크트리 구현 writer 없음, 기존 free checkout 재사용 가능. 루트HANDOFF 사용자소유 보존. heartbeat30분 유지.

재개: MEMORY·등록 목록·Git·writer를 확인한 뒤 국내ETF 공식 상품자료의 기존 cache부터 연결한다. 같은 NAV 계산이나 막힌 URL을 반복하지 않는다.
