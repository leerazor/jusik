# 포트폴리오 세션 달력 스트레스 v1

이 연구는 고정된 합성 사례로 포트폴리오 이벤트와 시장 세션 달력의 연결을 검증한다. 원본 `research_portfolio_engine.py`는 수정하지 않고 audit 출력 디렉터리에 복사한 뒤, 복사 모듈의 `_events`, `_known_bars`, `_market_time`, `volatility_scale`, `_as_of_external` hook만 어댑트한다. 입력은 커밋된 시장 세션 자료 하나이며 SHA-256 `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8`을 먼저 확인한다.

NYSE 2026-07-03은 명시적 휴장으로 이벤트를 만들지 않는다. 2026-11-27과 12-24는 뉴욕 현지 13:00, UTC 18:00에 닫히며, 겨울 정규 폐장은 현지 16:00, UTC 21:00이다. 2024-03-08과 03-11은 DST 전환에 따른 UTC 개장 시각을 확인한다. KRX의 지연 개장·폐장도 자료에 있는 세션을 사용한다. 2026-11-19처럼 `unavailable`인 날은 추정하지 않고 즉시 불완전으로 중단한다.

완료된 세션의 종가 시각까지만 feature와 변동성 입력에 포함한다. 결정 시각과 실행 시각은 `decision_at < execution_at`이어야 하고 다음 유효 개장에서만 체결한다. 첫 유효 개장에 bar가 없으면 늦은 bar로 대체하지 않고 실패한다. 합성 거래는 USD 환율, 수수료, split fractional cash-in-lieu, 반올림을 포함하며 독립 Decimal 현금흐름 식의 잔차는 `1e-6 KRW` 이하를 요구한다.

CLI harness는 결과와 hash manifest를 저장한다. 달력 hash, 세션 상태, cutoff, next-open 또는 회계 gate가 실패하면 결과를 재실행하지 않고 저장된 증거를 남긴 상태에서 중단한다. 이 범위에는 역사 실행, 원격 fetch, PAPER·제품 엔진·DB·runner·GPU·실주문이 없다.

## 기술 구현 확인

재시도 구현은 복사한 포트폴리오 엔진의 이벤트 hook만 어댑트하고 원본 엔진 파일은
수정하지 않는다. 각 raw bar에는 별도의 aware publication metadata가 필요하며, 세션
종가와 publication 시각 중 늦은 시각을 historical cutoff로 사용한다. metadata가
없거나 naive이면 즉시 실패하고, 변동성·FX도 각 과거 cutoff에서 독립적으로 다시
계산한다.

복사 엔진은 `calendar=` keyword를 포함한 현재 event hook 계약을 지원한다. warmup을
포함한 모든 bar는 달력에 존재하는 세션만 통과하며, 첫 유효 개장의 bar가 없거나
intervening 날짜가 `unavailable`이면 추정하지 않고 불완전으로 중단한다. 실행은
결정 시각보다 엄격히 늦은 첫 유효 개장과 일치해야 한다.

원장은 raw open/close, 세션 시각, 시점별 FX에서 Decimal 정밀도로 독립 재생한다.
split fractional cash-in-lieu, buy/sell 현금흐름, 수수료·FX 비용, close NAV, terminal
position, contribution과 모든 positive position의 symbol set을 결과와 대조하며 금전
잔차 허용치는 `1e-6 KRW`이다. 출력 결과를 기대값 산출에 사용하지 않는다.

이 문서는 synthetic fixture에 대한 기술 검증만 기록한다. 이전 시도에서는 terminal
cash가 `1 KRW` 변조된 결과가 회계 gate를 통과한 결함이 확인되었고, 그 수락 증거와
후속 수정 검증은 해당 audit 디렉터리에 보존되어 있다. 이번 구현은 달력·cutoff·causality·회계 gate를 통과해도
역사 자료, 성과 비교, PAPER·실거래 승격의 근거로 사용하지 않는다.
