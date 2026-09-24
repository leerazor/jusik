# 2026-09-24 R1-05 Stooq bounded receipt

## 목적

R1-05의 남은 LIME/MDA 366개 세션 누락에 대해 무료 대체 원천을 한 번만 bounded 확인했다. 기존 Yahoo·Alpha receipt나 canonical cache는 변경하지 않았다.

## 요청과 결과

- 요청: Stooq CSV `https://stooq.com/q/d/l/?s={lime.us,mda.us}&d1=20250101&d2=20260924&i=d`
- 응답: HTTP 성공이지만 JavaScript verification challenge HTML이며 OHLCV 행은 제공되지 않았다.
- LIME raw SHA-256: `834d1f405145a5fafc19427540890bdfc91109313eabc677ed2365b37358c68d`
- MDA raw SHA-256: `1b91ef4bfd3ab9c1738601dededbdf7b46fac68c2926befa43fb7245d0a02917`
- receipt: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/stooq-bounded/`

이 응답은 historical observed_at, 원인, 가격 또는 coverage 근거가 아니므로 R1-05/PIT/economic acceptance를 승격하지 않는다. 자동으로 JavaScript challenge를 우회하거나 합성 행을 만들지 않는다.

## 다음 조건

유료/인증된 historical provider 또는 issuer/provider가 제공하는 원본 request·session identity·historical observed_at·complete coverage receipt가 있어야 planner가 R1-05를 재평가할 수 있다.

