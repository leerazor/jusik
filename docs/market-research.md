# 거래일 시점 시장 연구

이 연구는 한국과 미국을 별도 실행하며 각 실행을 원화 1억원에서 시작한다. 각 거래일의 당시 유효한 주식 membership과 그날 이용 가능한 일봉만으로 거래량 상위 20개를 결정하고, ETF는 제외한다. 종가에서 breakout과 거래량 조건을 확인한 뒤 다음 거래일 시가에 체결한다. 보유 종목은 후보 순위에서 빠졌다는 이유만으로 매도하지 않으며, 종가가 SMA20보다 낮은 날이 2회 연속이면 다음 거래일 시가에 청산한다.

미국 실행은 시작 시점에 한 번만 원화를 달러로 환전하고 이후 달러 현금과 거래를 기록한다. 달러 현금·거래와 원화 환산 곡선을 모두 보존하며, 20% 낙폭 기준은 원화 running peak NAV를 사용한다. 비용·슬리피지·세금·환전 spread와 자료의 `captured_at`, `available_at`, source hash를 실행 결과에 기록한다.

필수 과거 membership, 일봉, 기업행동, 거래일 달력, 미국 환율 자료가 하나라도 빠지면 수익률이나 거래를 만들지 않고 `검증 불충분`으로 표시한다. 기업행동을 자동 조정하지 않으므로 occurrence·observed 시각을 모두 확인할 수 없거나 장중 순서를 정할 수 없는 미국 사건은 안전하게 해당 근사 실행을 보류한다. 화면의 합성 실행은 인과 흐름과 다음 시가 체결을 확인하기 위한 자료이며 실제 수익률이나 주문이 아니다. 실제 3년 백필과 broker 실행 연결은 이 기능의 범위가 아니다.

## staged 검증

새 연구는 1년 파일럿과 3년 최종 단계로 구분한다. 각 단계의 시작일은 종료일의
달력상 기념일로 서버가 계산하며, 평년의 2월 29일은 2월 28일로 처리한다. 최종
단계는 같은 시장의 완료·성과 검증 파일럿을 참조하고 현재 정책, 실행 비용 가정,
정규화된 자료 계약 해시가 모두 같아야 한다. 파일럿은 모델 선택이나 PAPER·live
활성화로 이어지지 않는다.

평가 시작 전 정확히 20개의 완료 거래일을 warmup으로 고정한다. warmup에는 거래,
평가액, 보유 상태가 없고 첫 평가일부터 직전 20개 세션을 사용한다. 파일럿과 최종은
각자 PIT 자료를 수집하며 기간이 겹친다는 이유로 최종 자료를 파일럿 자료로 대체하지
않는다. 공급원 자료가 없거나 필요한 범위를 채우지 못하면 실행 가능하다고 표시하지
않고 검증 불충분으로 남긴다.

## 무료 근사 자료

무료 근사 등급은 개인 투자 판단을 위한 bounded historical sample이다. 날짜별 KRX·공공 목록 또는 Alpha Vantage 상장 상태와 Yahoo 과거 일봉, FRED DEXKOUS를 사용한다. 한국은 기존 `approx-v2` 표본 계약을 유지하며, 미국은 `approx-us-r1-event-timing-v1` 정규화 계약에서 고정 seed로 초기 표본을 고르고 성공한 연간 checkpoint마다 당시 유효한 incumbent를 유지한 뒤 빈자리를 당시 후보로 채운다. 미국 표본은 세션당 최대 100개, 실행 전체 누적 admission은 최대 400개이며 실패한 checkpoint부터 다음 성공 관측까지 membership을 알 수 없는 구간으로 남긴다. Yahoo 사건은 발생 시각과 공급원이 제공한 관측 시각을 각각 보존하고, 두 시각이 확인된 이후의 행만 해당 종목에서 격리한다. 사건이 기간 뒤에 발생하면 그 이전 자료를 제거하지 않으며, 시각이 없거나 날짜만 있어 장중 순서를 알 수 없으면 해당 미국 근사 실행을 `insufficient`로 남긴다. 현재 후보를 과거에 소급하지 않고, 누락 일봉·배당·상장폐지·생존자 편향·환율 한계를 결과에 표시한다. 근사 결과는 strict PIT 검증 자료가 아니며 `근사 계산`으로만 표시한다.

웹 요청은 준비된 cache를 읽기만 한다. CLI의 `import-file`은 공급자가 별도로 준비한 응답 파일을 운영 loader와 같은 provenance·기간 검증으로 검사하고 복사한다. CLI의 `collect`만 고정된 KRX·Alpha Vantage·Yahoo·FRED 공식 endpoint에서 제한된 범위의 응답을 받아 secret-free cache와 checkpoint를 만들고, 그 결과를 검증된 prepared file로 저장한다. KRX는 `data-dbg.krx.co.kr`의 `stk_bydd_trd`·`ksq_bydd_trd` GET API에 `basDd`와 `AUTH_KEY` header를 사용하며 이전 웹 화면 POST endpoint로 대체하지 않는다. 한국 일별 시세는 KRX KOSPI·KOSDAQ 거래 응답의 OHLCV를 사용하며 Yahoo로 대체하지 않는다. KRX EOD 행은 공식 장 마감 시각에 이용 가능하다고 모델링하고 다음 거래일 시가에서만 실행한다. 날짜별 거래 응답의 상장주식수 변화, 거래행 누락, 종목 소멸은 해당 시점 이후 안전하게 제외하고 원인과 원문 hash를 cache에 남긴다. 명시적 KRX `OutBlock_1: []`는 정상적인 no-trade 관측으로 보존한다. Alpha Vantage 목록은 전체 헤더를 검증하고 행별로 상품·비정상 이름·거래소·날짜 오류를 제외하며 입력·허용·제외 사유를 checkpoint별로 기록한다. 상품 분류는 collector 내부의 private `ordinary`·`etf`·`warrant`·`other`·`unknown` 값으로만 구조화하고, `ordinary`만 기존 stock row로 출력한다. `assetType`은 trim·casefold 후 exact 값만 사용하며 이름은 명확한 상품 suffix와 preferred stock/shares 구문을 상품 단어 경계로 검사하고 이름만으로 ordinary를 추정하지 않는다. 이름에 단독 상품 단어가 회사명으로 쓰인 경우까지 보수적으로 제외할 수 있다는 한계가 있다. `NCM`·`NMS`·`NGM`은 상품 정보와 무관하게 NAS 거래소 alias로 정규화한다. 공급자 응답은 cache 저장·재사용 전에 요청별 parser로 검증하며, 실패 응답은 cache에 저장하지 않는다. 명시적 null·요청 범위 밖 자료·quota·인증·구문 오류는 각각 부분 응답·coverage·quota·auth·parse 예외로 고정 분류하고 원문과 예외 원인을 노출하지 않는다. 키가 없거나 응답이 부분적·손상되었거나 기업행동을 해석할 수 없으면 성공 결과를 만들지 않는다. `collect`·`status`·`collect-status`의 dotenv 파일은 `--env-file`로 명시하고 보간하지 않으며 process standard → file standard → process alias → file alias 순서로 선택한다. `--resume`도 요청별 hash가 계획과 일치하는지 확인하기 전에는 전체 호출량을 예산으로 잡아 과소계상하지 않는다. 파일 원문과 hash, 표본 계약, coverage와 제외 건수를 함께 보존하고 pilot과 final의 source·pool·정규화·누락·기업행동·환율 계약이 다르면 결합하지 않는다.
`collect-status`는 `--start`, `--end`, `--sample-size`, `--output`을 함께 지정해야 해당 범위의 검증 완료 marker와 출력 hash를 확인해 ready를 표시한다. raw cache만 있거나 부분 수집된 상태는 ready가 아니다.

미국 근사 수집 결과에는 선택적인 `collection_diagnostics`가 함께 저장될 수 있다. 이
진단의 분모는 각 Yahoo 요청의 실제 거래소 거래일이며 warmup 시작일부터 요청 종료일까지
고정한다. 심볼별 `expected_sessions`, `actual_sessions`, `missing_sessions`,
`retained_sessions`, `event_excluded_sessions`는 각각 `expected = actual + missing`,
`actual = retained + event_excluded`로 대사한다. parser가 검증한 행이 없는 실패는
원천에 이력이 없다는 뜻이 아니라 `actual_sessions=0`인 검증 확보량으로만 표시한다.
identity·quota·auth·budget·parse·null·coverage·partial history·unknown과 전체 실패는
고정 reason code로 기록하며 provider 원문이나 예외 문구는 진단에 복사하지 않는다.
요청 자체에서 제외된 심볼은 `request_excluded`와 aggregate count로 별도 표시하며,
그 원인을 알 수 없는 경우 event timing의 `unknown`과 구분되는
`unknown_request_exclusion`을 사용한다.
`observed_delisting`은 명시적인 delist 이벤트의 occurrence/observation 시각과 기존 cutoff가
모두 유효할 때만 기록하고, 누락·미래·상충 자료로 추정하지 않는다. 진단은 전략 선택에
사용하지 않으며 기존 준비 파일은 이 필드가 없어도 읽을 수 있다.

Alpha의 명시적 일일 요청 한도 문구는 quota로 분류하고 API key 언급만으로 quota·auth로 분류하지 않는다. Yahoo는 상위 admission row의 기대 거래소·USD 통화를 fresh 저장 전과 resume 반환 전에 검증한다.
