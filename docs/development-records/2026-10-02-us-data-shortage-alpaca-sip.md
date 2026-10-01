# 미국 자료 결손: Alpaca SIP 제한 조회와 RAPT 거래 종료 판정

- 상태: 원천 제한 조회·결정 기록 완료. 전체 자료 인수 `insufficient`, 경제 평가 `not-evaluated`.
- 기록 시각: 2026-10-01T22:28:09Z
- 작업 slug: `us-data-shortage-alpaca-sip-20261002`
- 기준: 작업 등록 `34f16c8`. 통합 SHA는 [작업 등록부](../worktree-tasks.md#us-data-shortage-alpaca-sip-20261002)를 따른다.
- 범위: 기존 추적 22종목의 과거 일봉 **원천 가능성**만 조회했다. 최신 v5 final prepared, 캐시, 전략, mandate, NAV, PAPER/live를 변경하지 않았다.

## 확인한 사실과 결정

- 기존 [결손22 기록](2026-10-01-us-gap-provenance.md)의 범위는 2025-08-13 준비 시작, 2025-09-11~2026-09-11 평가다. 22는 원래 제외 25에서 세 종목을 추적 목록에서 뺀 것이며 최신 v5 final 결손 수가 아니다.
- 새 `MASSIVE_API_KEY`는 비어 있지 않다. 그러나 [Massive Market Data Terms](https://massive.com/legal/market-data-terms-of-service)는 별도 허가 없는 non-display 이용과 투자전략 등의 파생물 생성을 제한한다. 이 연구에 적용되는 별도 서면 사용권이 확인되지 않아 **Massive API 호출은 0회**다. 이전 [2회 preflight 계획](2026-10-01-us-data-shortage-source-feasibility.md)은 사용권 확인 전 실행하지 않는다.
- [Alpaca 공식 FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)는 15분 이상 지난 SIP 과거 조회가 무료 계정에 가능하다고 안내하고, [Historical API](https://docs.alpaca.markets/us/docs/historical-api)는 과거 자료의 백테스트 이용을 안내한다. 기존 키로 `feed=sip`, `timeframe=1Day`, `adjustment=raw`, `asof=-`, 요청 기간 2025-08-13~2026-09-12, 단일 페이지 최대 10,000봉을 조회했다. `asof=-`는 ticker 변경 연결을 끄므로 가격 행만으로 증권 신원을 증명하지 않는다.
- 제한 조회 4회: RAPT 단일 200, 추적22 일괄 400, 오류 확인용 동일 조회 400(`invalid symbol: ALB-P-A`), 하이픈 없는 16종목 일괄 200. 16종목 응답은 페이지 토큰이 없고 총 1,683봉이다. 9종목에서 OHLCV 완전한 봉이 나왔고 7종목은 0봉이다. 일괄 400은 `ALB-P-A`에서 발생했다. 하이픈 포함 나머지 5종목은 개별 조회하지 않았으며, 6종목 모두 자료 부재로 분류하지 않는다.
- 9개 중 `BERZ`, `FNGS`는 각 272봉으로 요청 기간의 처음과 끝에 걸치지만, 기존 [증권 신원 불일치](2026-10-01-us-gap-provenance.md)가 해소되지 않았다. `AVNS` 238봉(마지막 2026-07-24), `DYNX` 10봉(2025-08-26), `FFWM` 159봉(2026-03-31), `HSPT` 210봉(2026-06-12), `PELIR` 155봉(2026-03-25), `RAPT` 138봉(2026-03-02), `XOMAO` 229봉(2026-07-13)은 각 마지막 날짜 이후의 신원·상장·기업행사와 누락 여부를 별도 구분해야 한다. `BHAC`, `CVII`, `FRBN`, `LCW`, `RILYM`, `SP`, `STGC`는 0봉이다.
- RAPT는 준비 시작일 2025-08-13부터 20개 준비 봉을 포함한다. [Nasdaq 공식 기업행사 공지](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-124)는 마지막 거래일 2026-03-02, 2026-03-03 합병 종료, 현금 대가 주당 58달러를 명시한다. [SEC Form 25-NSE](https://www.sec.gov/Archives/edgar/data/1673772/000135445726000226/0001354457-26-000226-index.htm)도 2026-03-03 접수됐다. 이전 EODHD 2026-03-03~06 행은 종가 58.005 반복·거래량 0으로 실제 체결 일봉이나 합병 현금 처리의 대체물이 아니다. 원천별 마지막 거래일의 종가도 달라 가격 기준을 섞지 않는다.
- 판단: **유료 전환·무근거 가격 채우기·현재 표본의 자동 교체·성과 계산은 보류**한다. Alpaca SIP는 일부 가격 결손의 보조 근거 후보로 유지하고, 거래 종료·신원·현금 합병·기업행사 당시 관측시각을 별도 원천으로 확인한다. 무료 일봉만으로 완전 PIT 모집단, 기존 125건 사건 관측시각, NAV 및 비용 차감 성과를 입증하지 않는다.

## 문서·계약 영향

- 사용자·운영 동작, API·설정·데이터 계약: 변경 없음. `MEMORY.md` 색인과 이 기록·인계만 갱신한다.

## 검증

- 비공개 audit의 두 원문 SHA-256 재검사: RAPT `95e04c847d7b318d769564b690334e1d8e2c68dd5fb3e82f3d12ed2d89cb1da8`, 16종목 `c21db7287d5345b00f9097a544086f74b96187e454699eaa2e73fe127d2bae29`.
- 단일 RAPT 138봉과 일괄 응답의 RAPT 138봉이 완전히 같고, 일괄 응답에 다음 페이지 토큰이 없음을 확인했다. 9개 양성 종목의 일봉은 모두 날짜·OHLCV 필드가 있다. EODHD 3월 3~6일 거래량 0을 저장된 원문에서 재확인했다.
- [판정 JSON](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-sip-feasibility/assessment.json) SHA-256 `67d08092d37125586550e7d554fbde7a0e0106f95bd61bf8d54d56e0e8939355`. 통합 `main`에서 원문 해시·22종목 분류·이번 작업의 문서 링크·메모리 80줄/8 KiB 제한·`git show --check`·브랜치 ancestry가 통과했다. 전체 등록부 링크 검사에서는 기존의 없는 링크 1개를 발견해 이번 작업 항목만 좁혀 재검증했다. 코드·계약 변경이 없어 pytest·Ruff·mypy·금융 실험은 실행하지 않았다.

## 안전·운영 상태

- API 키 값과 인증 헤더를 기록·출력하지 않았다. 원문은 private audit에만 두고 제품 캐시에 넣지 않았다. 결제·주문·원격 push·DB 변경 없음. 수동 변경 전 runner `paused=true`, service `inactive`를 확인하고 service stop을 실행했다. 원래의 pause와 timer 상태를 보존한다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-sip-feasibility/`; `assessment.json`에 22종목별 행수·기간, 요청 조건, 원문 해시를 기록했다. 원문 두 건은 같은 경로의 private JSON이다.
- 다음 시작: 기존 22를 재요청하지 말고 9개 양성의 증권 신원·거래 종료/기업행사·실제 거래일 coverage와 7개 0봉·6개 미조회의 별도 원천을 조사한다. RAPT의 합병 현금 처리와 사건 `observed_at` 증거를 확인하기 전에는 성과 입력으로 승격하지 않는다. Massive는 별도 연구·전략 이용권이 확인될 때만 이전 계획을 검토한다.
- workflow 판단: 도움 됨 — 기존 추적22와 원문을 재사용해 가격 공백과 인수 후 거래 종료를 구분했다.
- 근거: 실제 Alpaca API 4회, Massive 0회, 금융 실험 0회; 시간·비용 절감량은 미측정이다.
- 다음 조정: 같은 범위 조회를 반복하지 않고 신원·이벤트 원천에 집중한다.
