# 거래일 시점 시장 연구

이 연구는 한국과 미국을 별도 실행하며 각 실행을 원화 1억원에서 시작한다. 각 거래일의 당시 유효한 주식 membership과 그날 이용 가능한 일봉만으로 거래량 상위 20개를 결정하고, ETF는 제외한다. 종가에서 breakout과 거래량 조건을 확인한 뒤 다음 거래일 시가에 체결한다. 보유 종목은 후보 순위에서 빠졌다는 이유만으로 매도하지 않으며, 종가가 SMA20보다 낮은 날이 2회 연속이면 다음 거래일 시가에 청산한다.

미국 실행은 시작 시점에 한 번만 원화를 달러로 환전하고 이후 달러 현금과 거래를 기록한다. 달러 현금·거래와 원화 환산 곡선을 모두 보존하며, 20% 낙폭 기준은 원화 running peak NAV를 사용한다. 비용·슬리피지·세금·환전 spread와 자료의 `captured_at`, `available_at`, source hash를 실행 결과에 기록한다.

필수 과거 membership, 일봉, 기업행동, 거래일 달력, 미국 환율 자료가 하나라도 빠지면 수익률이나 거래를 만들지 않고 `검증 불충분`으로 표시한다. 현재는 기업행동을 자동 조정하지 않으므로 split·halt·delisting 자료가 포함되면 안전하게 전체 실행을 보류한다. 화면의 합성 실행은 인과 흐름과 다음 시가 체결을 확인하기 위한 자료이며 실제 수익률이나 주문이 아니다. 실제 3년 백필과 broker 실행 연결은 이 기능의 범위가 아니다.

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

무료 근사 등급은 개인 투자 판단을 위한 bounded historical sample이다. 날짜별 KRX·공공 목록 또는 Alpha Vantage 상장 상태와 Yahoo 과거 일봉, FRED DEXKOUS를 사용하며, 고정 seed로 시장별 최대 100개 종목을 표본화한다. 현재 후보를 과거에 소급하지 않고, 누락 일봉·배당·상장폐지·생존자 편향·환율 한계를 결과에 표시한다. 근사 결과는 strict PIT 검증 자료가 아니며 `근사 계산`으로만 표시한다.

웹 요청은 준비된 cache를 읽기만 한다. CLI의 `import-file`은 공급자가 별도로 준비한 응답 파일을 운영 loader와 같은 provenance·기간 검증으로 검사하고 복사한다. CLI의 `collect`만 고정된 KRX·Alpha Vantage·Yahoo·FRED 공식 endpoint에서 제한된 범위의 응답을 받아 secret-free cache와 checkpoint를 만들고, 그 결과를 검증된 prepared file로 저장한다. KRX는 `data-dbg.krx.co.kr`의 `stk_bydd_trd`·`ksq_bydd_trd` GET API에 `basDd`와 `AUTH_KEY` header를 사용하며 이전 웹 화면 POST endpoint로 대체하지 않는다. 한국 일별 시세는 KRX KOSPI·KOSDAQ 거래 응답의 OHLCV를 사용하며 Yahoo로 대체하지 않는다. KRX EOD 행은 공식 장 마감 시각에 이용 가능하다고 모델링하고 다음 거래일 시가에서만 실행한다. 날짜별 거래 응답의 상장주식수 변화, 거래행 누락, 종목 소멸은 해당 시점 이후 안전하게 제외하고 원인과 원문 hash를 cache에 남긴다. Alpha Vantage 목록은 전체 헤더를 검증하고 행별로 상품·비정상 이름·거래소·날짜 오류를 제외하며 입력·허용·제외 사유를 checkpoint별로 기록한다. 키가 없거나 응답이 부분적·손상되었거나 기업행동을 해석할 수 없으면 성공 결과를 만들지 않는다. `collect`·`status`·`collect-status`의 dotenv 파일은 `--env-file`로 명시하고 보간하지 않으며 process standard → file standard → process alias → file alias 순서로 선택한다. `--resume`도 요청별 hash가 계획과 일치하는지 확인하기 전에는 전체 호출량을 예산으로 잡아 과소계상하지 않는다. 파일 원문과 hash, 표본 계약, coverage와 제외 건수를 함께 보존하고 pilot과 final의 source·pool·정규화·누락·기업행동·환율 계약이 다르면 결합하지 않는다.
`collect-status`는 `--start`, `--end`, `--sample-size`, `--output`을 함께 지정해야 해당 범위의 검증 완료 marker와 출력 hash를 확인해 ready를 표시한다. raw cache만 있거나 부분 수집된 상태는 ready가 아니다.
