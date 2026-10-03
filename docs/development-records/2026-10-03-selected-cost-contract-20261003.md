# 등록 종목 비용 적용 결손과 공식 원천 보완

- 상태: 원천 보완·결손 진단 완료; 비용 실행 계약/수익 비교는 미완료.
- 기록 시각: 2026-10-03T11:38:22Z
- 작업 slug: `selected-cost-contract-20261003`
- 기준: main `8adc605`; application 변경 없는 자료 조사·기록.

## 변경과 결정

중앙 라우팅 explore(Luna medium)의 읽기 전용 조사로 기존 PortfolioConfig의 fee/slippage/fxspread 공통 가정, 매도세 미지원과 PAPER 전용 broker profile의 적용기간·상품 구분 결손을 확인했다. 새 범용 validator 구현은 원천 결손을 해소하지 못하므로 보류하고 실제 공식 원문과 등록 목록 비용 결손표를 확보했다.

[한국투자증권 주식거래설명서](https://file.truefriend.com/Storage/customer/guide/regards/stock_guide.html)를 한 번 다운로드했다(HTTP200,55,917bytes). BanKIS 온라인 일반 주식과 ETF 행의 수수료가 다르고, 코스피 세금 표가 기존 동결 profile과 다른 합계를 제시한다. `source-facts.json`은6개 표시 사실과 Decimal 환산을 저장한다. 심사일2026-09-09와 문서 개정일2026-09-14를 요율 유효시작으로 해석하지 않았다. ETF 행은 시장 열을 병합하므로 NXT 거래 적격성을 추론하지 않는다.

`selected-cost-readiness.json`에 실제 API 등록16/revision1을 대조했다. 국내6종목에는 검토 대상 원천 fact만 연결했고 해외10종목에는 이 국내 문서의 요율을 연결하지 않았다. 상품 종류는 사용자맥락상 예상 분류이며 비용 적용용 검증 신원으로 주장하지 않는다. 모든 행의 rates_applied=false,ready_count=0이다. 원천 확보와 실행 계약 완성을 구분한다.

## 검증

원문SHA `4e601deb80de0d38f395bfd8a170003f5e238eb3e5d29ec900dee9ee94157c10`. 독립 Sol review가 HTML 표 문맥·병합셀,6개 퍼센트/100 환산,문서날짜 비적용,16개 고유tuple·미적용 상태를 확인해 PASS했다. 기존 profile 요율은 변경하지 않았다. 별도 네트워크 재조회 없이 저장 원문으로 검토했다. 코드 변경이 없어 전체 테스트·UI 빌드는 실행하지 않았다.

## 문서·계약·운영 영향

새 application/API/UI/PAPER/실거래 계약이나 배포 없음. 사용자 계좌 비용을 확정하지 않았고 과거 frozen 비용도 덮어쓰지 않았다. 자동 주문·PAPER/live·Pages·remote push 없음. API8001 등록16/revision1, development runner/service/timer 및 optimizer inactive를 실측했다. 비용 자료 수집은 공개문서이며 계좌·credential 조회 없음.

## 증거와 다음 작업

- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-selected-cost-contract/`
- manifest SHA `fd71720ecd6e207ff3fc1a3c9132aeaf7b76ceb4c0adfa0bed906a2da617d0d7`
- 후속: 등록 국내ETF4개 공식 상품 설명서의 비용/과세 유형·종목코드 연결을 먼저 채운다. 기존 일반 주식 요율과 매도세를 ETF 전체에 적용하지 않는다. 과거 유효기간과 broker/계좌 적용 범위는 분리해 미확인 유지한다. 실제 비용 계약 이전에도 명시적 가정 비용 시나리오 설계는 가능하지만 실제 세후수익 또는 경제 acceptance로 표시하지 않는다.
- 기존13/111 배당 적격 및 FX/PIT 제약도 남음. 이 단계는 가격·배당 비교를 실행하지 않았고 OOS를 소비하지 않았다.

- workflow 판단: 도움 됨 — 독립 조사로 불필요한 일반 계약 구현을 피하고 공식 원천의 상품별 차이를 확보.
- 근거: 새 공식 원문1건 성공·독립 검토 PASS·실제 비용 적용0; 시간/호출 절감은 미측정.
- 다음 조정: 유지 — 캐시 재사용과 최소 공식 자료 보완, 동일 실패 조회 반복 금지.
