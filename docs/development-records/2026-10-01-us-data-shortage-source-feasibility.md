# 미국 자료 결손의 기존 키·무료 원천 판정

- 상태: 자료 원천 제한 조회와 결정 기록 완료; 데이터 인수는 `insufficient`.
- 기록 시각: 2026-10-01T07:53:28Z
- 작업 slug: `us-data-shortage-source-feasibility-20261001`
- 기준: 등록 전 `f58f0c0bd2e6c236a065a35ff60a0b7f1d6c0998`, 문서 워크트리 `a24a3499fcad7d47302ca187cb4ea836ec60e087`. 통합 커밋은 [작업 등록부](../worktree-tasks.md#us-data-shortage-source-feasibility-20261001)에 기록한다.
- 범위: 기존 설정 키로 결손 보통주 `RAPT`의 역사 일봉을 Alpha Vantage와 EODHD에서 각 1회 조회했다. 원문과 비밀값 없는 요약은 전용 audit에 보존했다. 이전 22종목 결손·v5 준비 자료·정책·코드·전략·NAV는 변경하지 않았다.

## 변경과 결정

- [시도별 기존 근거](2026-10-01-us-gap-provenance.md)의 22종목에는 `RAPT`가 포함된다. 이 22는 원래 제외 25종목 중 MET-P-F·GPACW·TNMG를 *추적 목록에서* 뺀 것이며, 최신 v5 final prepared의 결손 수가 아니다. 평가기간은 2025-09-11~2026-09-11, 준비 시작은 2025-08-13이다.
- Alpha Vantage `TIME_SERIES_DAILY`, `outputsize=full`의 RAPT 요청은 HTTP 200이지만 `Information`의 유료 접근 안내만 반환했다. 가격 행은 0개다. 응답 SHA-256은 `37aaccd80b9e6babd46c5275fa4692477b19eb2354b0773e78c8c473b7a87e5f`다. 이는 이번 키·요청의 판정이며 전체 원천 불가 판정이 아니다.
- EODHD `/api/eod/RAPT.US`의 정확한 준비·평가 요청은 HTTP 200, OHLCV 108행, 날짜 2025-10-01~2026-03-06이었다. 구독 범위 경고 필드가 1행에 있고 2025-08-13~09-30 준비·평가 앞부분이 비어 있다. 응답 SHA-256은 `1e009d80a7234dbea21596d9eebfdf3b2448db3cca058073a35b8e7b1eef8a4f`다. 뒤쪽 공백의 원인을 상장폐지로 확정하지 않는다. [공식 EODHD 일봉 계약](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)은 무료 범위의 과거 1년 제한과 raw OHLC·조정 종가 구분을 명시한다.
- 기존 키로 결손22를 일괄 조회하거나, 유료 전환하거나, 같은 Yahoo 실패 요청을 반복하지 않는다. 한 심볼의 가격만으로 전체 종목·거래일 coverage, 과거 증권 identity, 기업행사 최초 관측시각, 원화 NAV·경제 적격성을 증명할 수 없기 때문이다. 기존 125건 사건 관측시각 결손도 남는다.
- [Massive 무료 계획](https://massive.com/pricing?product=stocks)은 2년 이력·분당 5회로 안내하며, [전체시장 일봉](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)과 [날짜별 종목 참조](https://massive.com/docs/rest/stocks/tickers/all-tickers)가 있다. 그러나 현재 `MASSIVE_API_KEY`가 설정되지 않았고 이용 권한·실제 종목 identity·가격·사건 vintage는 확인하지 못했다. 전용 [최대 2회 preflight](/home/kwl/.local/share/jusik/portfolio-audit/20261001-data-shortage-decision/massive-free-preflight-plan.json)을 준비했으나 실행하지 않았다. 키만 설정해도 현재 `UnavailableMarketHistorySource`가 실제 원천 수집기로 바뀌지는 않는다.
- [미래 관측 등록 초안](/home/kwl/.local/share/jusik/portfolio-audit/20261001-data-shortage-decision/future-observation-registration-draft.json)은 `unregistered`, `execution_allowed=false`다. 원천·기간·빈도·FX·평가 경계가 미정이므로 실제 수집이나 기존 PAPER 기간 재사용을 시작하지 않았다. [미래 관측 프로토콜](../research-future-observation-protocol.md)의 등록 전 게이트를 따른다.

## 문서·계약 영향

- 사용자·운영 동작, API·설정·데이터 계약: 변경 없음. 기존 결손과 새 원천의 결정 경로만 이 기록·인계와 `MEMORY.md`에 추가했다.

## 검증

- 두 원문 SHA를 저장된 요약과 다시 대조했다. EODHD 108행은 모두 날짜·OHLCV가 있고 구독 경고 행은 1개다. 단일 심볼 결과를 전체 22종목이나 PIT 판정으로 확장하지 않았다.
- 원천 응답과 [판정 JSON](/home/kwl/.local/share/jusik/portfolio-audit/20261001-data-shortage-decision/source-feasibility-assessment.json)의 SHA-256은 `d1befecc07f5b13fb0a0b1514a1d6dcfb43235acfee60157056003fb06149411`다. 별도 문서 링크·diff·Git 검사는 통합 때 기록한다.
- 코드·테스트·자료 계약 변경이 없어 pytest·Ruff·mypy·금융 실험은 실행하지 않았다.

## 안전·운영 상태

- 기존 `.env`의 키 이름만 확인하고 값·인증 URL·원시 응답을 Git·대화에 노출하지 않았다. 원문은 권한 제한된 audit 경로에만 저장했다. 결제·계정 생성·실주문·PAPER/live·DB·원격 push 변경 없음.
- 수동 문서 변경 전에 runner `paused=true`, RUNNING 0을 확인하고 service를 중지해 `inactive`를 확인했다. timer는 유지했다. 시작 당시 이미 paused였으므로 완료 후에도 그 설정을 보존한다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261001-data-shortage-decision/`; 원문 2개, 안전 요약 2개, source 판정, 무료 원천 preflight 계획, 미래 등록 초안을 분리 보존한다.
- 새 무료 키와 허용되는 사용권이 확인되면 계획의 **2회 제한** 조회로 RAPT의 과거 날짜별 가격·증권 identity를 검증한다. 통과하더라도 22종목·272세션·기업행사 vintage는 별도 게이트다. 키가 없으면 과거 가격 조회는 여기서 멈추고 미래 관측의 미정 등록값을 확정하기 전에는 수집하지 않는다.
- workflow 판단: 도움 됨 — 기존 응답을 재요청하지 않고 한 심볼·두 원천으로 기존 키의 결손 해소 가능성을 구분했다.
- 근거: 새 API 요청 2회, 전략·성과 실행 0회; 절감 시간과 비용은 미측정이다.
- 다음 조정: 같은 키·범위의 가격 sweep은 중단하고 새 무료 원천의 접근·권한·최소 조회가 가능할 때만 재개한다.
