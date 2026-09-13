# 잔여 현금 위험 추정 진단

`portfolio-residual-cash-risk-proxy-v1`의 첫 단계는 저장된 dev1/dev2 결과와 관측을 읽는 진단이다. `backend/jusik/research_portfolio_residual_cash.py`는 전략 엔진을 실행하지 않으며, 새 historical simulation 호출은 0회다.

진단 결과는 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed/diagnostic/diagnostic.json`에 저장한다. 각 입력 simulation과 observation의 SHA-256, prior `results.json` 해시와 진단 모듈 해시를 함께 기록한다.

결정 시점별 `pre_vol_gross`, `post_vol_gross`, volatility scale, eligible count와 unallocated target을 제공한다. volatility, gate eligibility, cadence/band, cap, reentry latch와 unallocated target은 서로 겹치는 설명 단계이므로 현금 비중의 가산 분해로 해석하지 않는다. `unallocated_target`은 gross cap과 post-volatility target 사이의 목표 공백이며 현금 비율 자체가 아니다.

후속 비교 후보의 포트폴리오 변동성은 동일 시점 이전의 정렬된 KRW 수익률로 계산하는 보수적 scalar proxy `max(0.9*S, P)`로 사전등록한다. 원자료의 미래 가격·FX 사용, 누락·중복·비유한 자료의 보간은 허용하지 않는다. 진단 승인과 immutable preregistration 전에는 전체 시뮬레이션을 실행하지 않는다.
