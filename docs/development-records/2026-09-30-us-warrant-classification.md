# 미국 워런트 명칭 분류 보정

- 작업: `us-warrant-classification-20260930`; 기준 `1742647`; 구현 `56a79b5`, 독립 review PASS, main 통합 `abfca4c9ff7165fd57ff1a59a3ef942c8d443062`.
- 범위: Alpha Vantage 두 원문에 있는 `GPACW, Global Partner Acquisition Corp Wt Exp 07012020`은 `Stock`으로 표기되지만 워런트 명칭이다. [고정 범위와 원문 해시](../../../../.local/share/jusik/portfolio-audit/20260930-us-warrant-classification/scope.json)를 근거로 `Wt Exp`와 연속 8자리 날짜만 warrant로 분류한다. 티커 모양이나 단독 `Wt`로 다른 종목을 제외하지 않는다.
- 새 미국 수집은 v4 정규화·독립 pool 계약·`completed-us-exclusions-v3.json`을 사용한다. v4 reader와 완료 검증은 해당 명칭을 가진 universe의 v4 재표시를 거부한다. v2·v3 reader, 계약 해시, 완료 marker 의미와 기존 자료는 보존한다. `market_history_sources.py`의 공통 data contract 계산은 그대로 둔다.
- [시장 연구](../market-research.md), [연구 조건](../research-mandate.md), [로드맵](../investment-development-roadmap.md)의 신규 수집 설명을 갱신하고 manifest의 Markdown 해시 두 행만 동기화했다. mandate JSON·정책·기존 네 해시 행과 투자 기준은 불변이다.
- focused pytest 54개 통과, Ruff check/format 5파일 통과, 소스 2파일 strict mypy 통과, mandate/dispatch 검증 통과. [검증 결속](../../../../.local/share/jusik/portfolio-audit/20260930-us-warrant-classification/verification.json)에 명령·파일 해시와 보호 원본 19개·Alpha 원문 2개 확인을 보존한다. 시장 요청·전체 수집·전략·NAV·주문은 실행하지 않았다.
- 이전 준비 자료의 요청 제외 25심볼과 사건 125행 관측시각 결손은 그대로다. v4 구현은 데이터 인수나 비용 차감 수익률의 검증이 아니다. 새 수집 전에 기존 cache만으로 v4 표본·miss 변화를 계산하고, 필요한 사건 원천 증거를 별도 범위에서 검토한다.
- workflow 판단: 도움 됨 — 저장된 원문에서 새 분류 누락을 확인하고 좁은 계약 수정에 연결했다.
- 근거: 최종 관련 54개 검사 PASS, 원본 19개·Alpha 2개 보존, 외부 요청 0. 소요 시간·호출 절감 비교값은 미측정이다.
- 다음 조정: 축소 — 같은 원문 재감사 없이 v4 선정 차이와 새 요청 필요성만 판정한다.

## 통합·보존·다음 작업

- main의 전체 backend tree와 변경 11파일이 독립 검토·검사한 커밋과 정확히 일치했다. 보호 19개·Alpha 원문 2개, 문서 링크 7개, mandate JSON 관련 4행 불변·문서 체크섬 2행을 확인했다. 충돌이나 중간 코드 변경이 없어 통과한 테스트를 다시 실행하지 않았다. `review-final.json`, `integration.json`, `routing-code-review.json`이 해당 근거다.
- 실행 환경 버전은 `verification.json`, 정리 대상·프로세스 점검은 `cleanup-preflight.json`에 보존했다. 전용 worktree/branch를 제거했고 루트 사용자 HANDOFF·다른 작업은 보존했다. runner paused/running0 및 service/timer inactive 유지. 실주문·PAPER/live·결제·권한·자격증명·원격 push 변경 없음.
- 기존 실패 24건 중 GPACW 분류 누락을 수정했으며, **v4 재선정 후 시세 결손은 미평가**다. 이전 v2 준비 자료의 요청 제외 25심볼과 최신 v3 실패24를 혼동하지 않는다. 사건125 관측 결손·배당 회계 연결·비용/NAV 적격성은 여전히 미충족이다.
- 다음 범위는 캐시140개를 재사용한 v4 선정 차이와 정확 요청키 비교다. 전체 수집·mock 결과의 준비 자료 승격·기존 실패 요청 반복 없이, 새 선정 종목의 캐시 결손이 실제로 생겼을 때만 제한 조회를 별도 판정한다.
