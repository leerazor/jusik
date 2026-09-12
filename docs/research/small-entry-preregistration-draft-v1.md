# 신규 소액 진입 사전등록 초안 v1

이 문서는 `small-entry-preregistration-draft-v1`의 오프라인 초안 계약이다. 검증기는
명세를 읽고 canonical JSON과 누락 결정 목록을 만들 뿐이며, DB·시세 수집·포트폴리오
엔진·주문·PAPER·실험 실행을 호출하지 않는다. 값이 모두 채워져도 상태는 계속
`draft`이고 `runtime_activation_allowed`는 `false`다.

## 현재 결정되지 않은 값

`threshold_krw`, `approval_time`, `future_period_start`, `future_period_end`의 기본값은
모두 `null`이다. 네 값은 별도 승인 시 결정한다. 부분적으로 채운 초안도 유효하지만,
승인 시각은 미래 평가 시작보다 엄격히 앞서고 시작은 종료보다 앞서야 한다. 시각은
timezone-aware 값으로 받고 canonical JSON에서는 UTC로 표현한다. 이 도구는 현재 시각을
암시적으로 기록하지 않는다.

임계값은 양의 유한 Decimal이어야 하며 0, 음수, bool, NaN, infinity를 허용하지 않는다.
알 수 없는 필드와 `registered` 또는 활성화 상태는 거부한다.

## 고정된 역사 맥락

참고한 입력은 다음 SHA-256으로 고정한다.

- 완료된 entry amount distribution: `83f42856e91a34c35f711335dfd9eebebb1a220e902b2f1d767ab74cec1cc5be`
- original unheld preregistration: `9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7`

이 값들은 역사적 참고 출처이며 새 threshold나 승자를 계산하기 위한 검색 대상이
아니다. 원래 control은 `low_turnover_combined`, 4주 주기, 2%p band를 그대로 둔다.
새로운 `NEW` floor를 control에 추가하지 않는다. 원래 unheld exemption은 맥락으로만
기록하며 새 control로 암묵 변환하지 않는다.

기존 기록에는 이 신규 소액 진입 사전등록 자체가 존재하지 않았으며, original
unheld 문서는 이 초안의 사전등록이 아니다. 따라서 `reused_data`와
`historical_context_only`는 `true`, `prospective_validation_eligible`와
`historical_small_entry_preregistration_found`는 `false`로 고정한다.

매수 직전 보유 수량이 0이면 `new_entry`, 양수이면 `additional_buy`다. 수량이
없거나 음수이면 `unknown`이다. 계획 notional은 `quantity × local price × FX`의
KRW 값이며 사전 결정 시점에 계산하고 수수료를 포함하지 않는다. 역사적 filled
notional에는 체결 가격에 들어간 slippage가 포함될 수 있으므로, fee와 FX 비용을
다시 notional에 더해 이중 계산하지 않는다.

초안의 threshold 의미는 계획 notional이 threshold보다 엄격히 작은 경우
소액 진입으로 분류하는 것이다. threshold와 같은 금액은 소액 진입이 아니며, 이
초안은 addon의 carry·merge 규칙을 정의하지 않는다.

비용 설명은 기존 역사 모델 가정의 1x/2x 시나리오로 고정한다. 각 시나리오의
fee/slippage/FX spread는 각각 0.001 또는 0.002이며 실시간 brokerage rate나 주문
요청이 아니다. 미래 평가를 할 때만 같은 input·universe·period·cost를 control과
small-entry 양쪽에 적용하고 net return, MDD, turnover, new-entry count를 함께
기록한다. 누락·중복·미래 데이터 누출·hash·회계·계약 위반 또는 drawdown 10% 이상이면
중지한다. 자동 승격은 하지 않는다.

## 위험 한도

사용자 ceiling은 초기 자본 100,000,000 KRW, 최대 손실 20%, leverage 20%다. frozen
PAPER 계약은 drawdown 10%, gross exposure 60%, symbol exposure 20%, leveraged ETF
20%를 보존한다. 이 초안은 어느 한도도 실행하거나 완화하지 않는다.

## 재현과 산출물

```bash
PYTHONPATH=backend backend/.venv/bin/python \
  -m jusik.research_small_entry_preregistration \
  --output-dir validation/small-entry-draft
```

`--input`을 생략하면 기본 draft를 사용한다. 입력은 UTF-8 JSON object여야 한다.
`--output-dir`는 반드시 새 디렉터리이거나 비어 있어야 하며 기존 파일에 덮어쓰지
않는다. 결과는 `draft.json`, `draft.sha256`, `missing-decisions.json` 세 파일이다.
JSON은 sorted keys, compact separators, UTF-8로 canonicalize하고 Decimal은 안정된
문자열로 직렬화한다. `draft.sha256`는 self-hash 필드가 있다면 이를 제외한 전체
canonical draft bytes의 SHA-256을 기록한다. 입력 내용이 달라지면 hash도 달라진다.
