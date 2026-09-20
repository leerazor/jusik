# Canonical time-evidence attachment manifest

- 상태: companion evidence manifest 확보·정본 readiness 연결 보류
- 범위: 기존 canonical run을 덮어쓰지 않고, 동일 run identity·입력·기간·전략의
  time-evidence candidate를 별도 attachment manifest로 고정했습니다.

## 대조

- canonical run SHA: `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`
- candidate run SHA: `5e4613e2fedad5ecb99f6308686b4e6151df52ba5356d7095dac266a2f4663a3`
- replay SHA: `2ad813a8788774a85cde6046379735a573d4e972be09887228c3bcbab0e46ae4`
- replay `comparison.all`: `true`
- initial anchor: `2025-09-11T13:30:00Z`
- NAV timestamps: 252개, `2025-09-11T20:00:00Z`~`2026-09-11T20:00:00Z`
- identity: input/data/pool/policy hash와 US pilot period가 canonical과 일치

## 판정

attachment manifest는 `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/attachment-manifest.json`에 보존했습니다. 이는 두 시간 blocker를 제거할 수 있는 재현 가능한 후보지만, 현재 readiness 기본 경로·canonical artifact·경제 평가는 변경하지 않았습니다. KOFR evidence가 없으므로 Sharpe와 경제 승격은 계속 차단됩니다.
