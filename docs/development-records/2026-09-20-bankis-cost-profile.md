# BanKIS online cost profile

- 상태: 완료·새 PAPER 비용계약 대기
- 기록 시각: 2026-09-20T14:00:00Z
- 작업 slug: `bankis-cost-profile-20260920`
- 기준/통합: `783b272` / 다음 통합 커밋
- 범위: 사용자가 선택한 BanKIS online 범위의 공식 수수료·세금값을 immutable profile로 추가했습니다. 기존 frozen historical backtest, modeled rate, 주문 실행은 변경하지 않았습니다.

## 변경과 결정

- `backend/jusik/broker_cost_profiles.py`에 KRX `0.000140527` fee/NXT `0.000130527` fee, 국내 매도세 `0.0023`, US online `0.0025` fee/SEC fee `0.0000206` profile을 기록했습니다.
- 각 profile은 broker/account scope, currency, source URL, source-as-of를 보존합니다.
- profile은 새 PAPER 연구 비용계약에서 명시적으로 선택할 때만 사용하며 frozen history에 자동 적용하지 않습니다.

## 검증

- `backend/tests/test_broker_cost_profiles.py` — `2 passed`
- Ruff — 통과
- strict mypy — 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 유지.

## 다음 시작

- 새 PAPER 비용계약 생성 시 profile을 request/source hash에 결속하고, 기존 frozen runs와 분리된 cost sensitivity를 실행합니다.
