# Corrected calendar portfolio stress

## 실행

corrected simulation의 고정 NAV path에 기존 offline block-bootstrap CLI를 적용했다.

- seed: `20260918`
- block length: 20 observations
- horizon: 1,171 observations
- scenarios: 512
- device: CPU
- request SHA: `1f0f707fe51ac8d2643873c9be53a88f0c021c64ba551fb53158247e3a57f7d6`
- indices SHA: `6bfee9901e80cb1e6ff09799b2568074d916ed4116f23f3600e7343799e690a7`

## 결과

- loss frequency: `0.015625`
- drawdown ≥20% frequency: `0.0`
- joint loss/drawdown frequency: `0.0`

## 제한

이는 historical NAV 경로의 block-bootstrap 기술통계다. 미래 확률·실제 위험·경제 성과·후보 채택·readiness 승격을 의미하지 않는다. 기존 NAV·bundle을 변경하지 않았고 PAPER/live·주문·runner를 실행하지 않았다.
