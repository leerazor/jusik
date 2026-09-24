# R2-02 비용 계약 입력 검증

## 상태

완료. 기존 비용률·SEC 전달률의 의미와 값은 변경하지 않고, 새 PAPER 비용 계약 manifest가 malformed evidence를 fail-closed로 거절하도록 경계를 보강했다.

## 변경

- 통화와 시장의 일치 여부를 검증한다.
- 수수료·세율이 유한하고 `0..1` 범위인지 검증한다.
- 출처 URL은 HTTPS이고 하나 이상이어야 한다.
- `source_as_of`는 ISO 날짜여야 한다.
- manifest의 `contract_id`도 hash와 함께 재계산 값과 일치해야 한다.

검증 실패는 기존 외부 계약과 동일하게 `paper_cost_contract_profile_invalid` 또는 명시적 계약 오류로 종료한다. 기존 frozen history에는 적용하지 않는다.

## 검증

- `backend/tests/test_broker_cost_profiles.py`: 8 passed
- Ruff check/format: 통과
- `mypy backend/jusik/broker_cost_profiles.py`: 통과

실제 계좌별 수수료 명세와 체결·ECN·SEC 최소수수료 자료는 확보되지 않았으므로 비용률을 변경하거나 R2-02 경제 acceptance로 승격하지 않았다.
