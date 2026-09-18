# Corrected XKRX calendar preflight

## 결과

기존 canonical calendar는 보존한 채 generator의 corrected calendar를 별도 audit identity로 생성했다.

- calendar bytes SHA: `36b64e421192062ff183112d1eef7d441af6e0f73cfaf739310b0b5ab8c281e1`
- calendar payload SHA: `5ac707711cb82f7849b7824567515f67dcbaad162452757b6727cccb9e20f2bd`
- corrected bundle: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/run-v3`
- bundle manifest SHA: `e5aa5af8a2c3a21696f395987216cae6ca002093a1138127449d09b54cf01600`
- generation 1회·verification 1회, NAV 1,172, simulation output SHA unchanged
- independent accounting verification: `verified`, 171 trades, 1,172 NAV consumed, max residual `0 KRW`
- accounting digest: `657fec08a769f3d328962cd2e799b021e997b7a1b70ef981c80562e9d10698e8`
- verifier source SHA: `0aa01d5cba655220ab6548db3485589c59851974ee09c06463f9bb43b67c73d6`

2026-06-03·2026-07-17은 XKRX `closed`이고 XNYS 세션은 유지된다. 따라서 두 누락 close가 세션 완전성에서 제거되지만, 기존 registered independent accounting verifier는 이전 manifest만 허용한다.

## 제한과 다음 작업

새 bundle은 historical/approximate technical evidence일 뿐이다. 기존 bundle을 덮어쓰지 않았고 runner·주문·PAPER/live·readiness 승격을 수행하지 않았다. accounting 입력 단계는 통과했으며, 다음 작업은 이 corrected bundle에서 UTC daily sampling 및 CAGR/MDD/Sharpe/Calmar metrics adapter를 별도 구현·검증하는 것이다. KOFR 부재 시 Sharpe는 unavailable로 유지한다.
