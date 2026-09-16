# DD chronology 독립 검산

`backend/jusik/drawdown_chronology.py`는 저장된 NAV·거래·시장 bar만 읽어 초기 자본을 포함한 peak, DD/MDD, 20% latch chronology를 독립적으로 계산한다. 전략·포트폴리오 엔진·증권사 API를 import하지 않으며 Decimal 정밀도 50을 사용한다.

## 계산 계약

- peak는 초기 자본에서 시작하고, 관측된 NAV가 더 높을 때만 갱신한다.
- NAV가 `peak * 0.80` 이하가 되는 최초 관측을 latch로 기록한다. 임계 판정에는 반올림 오차를 적용하지 않는다.
- 0 NAV는 100% DD로 계산하고, 음수 NAV와 0 이하 초기 자본은 입력 오류로 거부한다.
- latch 당일 fill은 허용하지만 이후 buy와 latch 해제·재진입은 거부한다.
- signal은 fill보다 앞선 거래 세션이어야 하며, 거래는 입력 순서를 보존한 fill chronology와 수량 ledger를 검증한다.
- latch 시점 보유 수량을 재구성한 뒤 종목별 dataset bar에서 latch 다음 첫 유효 open을 찾고, 그 시점의 전량 sell이 latch 이전 signal을 보존할 때만 `observed`로 표시한다. open 증거가 없거나 기간 말까지 체결되지 않으면 `not_observed`로 남긴다.
- DD/MDD 저장값 대조 허용오차는 percentage point 기준 `1e-20`이다. 저장 NAV 검산은 전체 현금·비용 회계 증명이 아니다.

고정 fixture는 12개 case이며 각 case는 300 세션 이하이다. fixture에는 threshold 경계, 회복, FX 수준 변화, 휴일을 세션으로 추정하지 않는 날짜, 다음 open 결측, 기간 말 미체결, 잘못된 chronology, 0·음수 NAV를 포함한다.

## 저장 파일럿 진단

네트워크나 새 실행 없이 다음처럼 한 저장 파일럿과 동결 bars를 진단한다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.drawdown_chronology \
  --pilot /path/to/us-web-pilot-run.json \
  --dataset /path/to/us-pilot-1y-stable.json \
  --output /path/to/drawdown-chronology-pilot.json
```

동결 파일럿은 독립 MDD·세션별 DD와 최종 latch boolean이 일치하고 5개 보유 종목의 다음 유효 open 전량 청산을 관측했다. 저장 파일럿에는 최초 latch 날짜와 실행 중 release chronology가 없으므로 전체 chronology 일치는 주장하지 않는다. 결과 상태는 `blocked`다. 이 slice에는 별도로 검증된 거래소 calendar, 동일 조건 benchmark, prospective future observation 증거가 없으므로 capability flag만으로 성공을 만들지 않는다. 입력 자료의 `approximate` 등급과 원래 근사 grade는 그대로 유지한다.
