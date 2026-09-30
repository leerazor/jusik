# 미국 워런트 명칭 분류 보정

- 작업: `us-warrant-classification-20260930`; 기준 `1742647`; 독립 검토와 main 통합은 감독자 예정.
- 범위: Alpha Vantage 두 원문에 있는 `GPACW, Global Partner Acquisition Corp Wt Exp 07012020`은 `Stock`으로 표기되지만 워런트 명칭이다. [고정 범위와 원문 해시](../../../../.local/share/jusik/portfolio-audit/20260930-us-warrant-classification/scope.json)를 근거로 `Wt Exp`와 연속 8자리 날짜만 warrant로 분류한다. 티커 모양이나 단독 `Wt`로 다른 종목을 제외하지 않는다.
- 새 미국 수집은 v4 정규화·독립 pool 계약·`completed-us-exclusions-v3.json`을 사용한다. v4 reader와 완료 검증은 해당 명칭을 가진 universe의 v4 재표시를 거부한다. v2·v3 reader, 계약 해시, 완료 marker 의미와 기존 자료는 보존한다. `market_history_sources.py`의 공통 data contract 계산은 그대로 둔다.
- [시장 연구](../market-research.md), [연구 조건](../research-mandate.md), [로드맵](../investment-development-roadmap.md)의 신규 수집 설명을 갱신하고 manifest의 Markdown 해시 두 행만 동기화했다. mandate JSON·정책·기존 네 해시 행과 투자 기준은 불변이다.
- focused pytest 54개 통과, Ruff check/format 5파일 통과, 소스 2파일 strict mypy 통과, mandate/dispatch 검증 통과. [검증 결속](../../../../.local/share/jusik/portfolio-audit/20260930-us-warrant-classification/verification.json)에 명령·파일 해시와 보호 원본 19개·Alpha 원문 2개 확인을 보존한다. 시장 요청·전체 수집·전략·NAV·주문은 실행하지 않았다.
- 이전 준비 자료의 요청 제외 25심볼과 사건 125행 관측시각 결손은 그대로다. v4 구현은 데이터 인수나 비용 차감 수익률의 검증이 아니다. 새 수집 전에 기존 cache만으로 v4 표본·miss 변화를 계산하고, 필요한 사건 원천 증거를 별도 범위에서 검토한다.
- workflow: 이미 확정된 좁은 구현 경로와 기존 v3 회귀를 재사용해 중복 조사와 실행을 줄였다. 고정 원문·기존 해시와 새 계약을 분리해 검증했다. 이후에는 v4 선정 변화와 자료 결손에 직접 연결되는 작업만 진행한다.
