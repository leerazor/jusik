# FRED FX vintage check

- 상태: 원천 확인 완료·PIT timestamp gate는 미해결
- 기록 시각: 2026-09-21T07:31:00+09:00
- 대상: FRED `DEXKOUS`, `2025-09-11..2026-09-11`
- 응답 SHA-256: `4afedc2bf206abf73efdcfe54f7ba55398cd968273dd551ea8f0742a81409d6a`

## 관찰

FRED API 응답은 262개 관측을 반환했고 모든 행에 `realtime_start=2026-09-20`,
`realtime_end=2026-09-20`이 기록되었습니다. FRED 문서의 real-time period는
vintage 날짜 범위이며 intraday publication timestamp가 아닙니다.
기존 parser도 이 값을 다음 UTC 자정으로 보수적인 availability upper bound로만
사용하고, 관측일을 availability의 증거로 취급하지 않습니다.

공식 참고: [FRED series observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html),
[FRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

## 판정

FRED는 값과 vintage 재현성에는 사용할 수 있지만, canonical US run의 각 session
open/close 이전에 값이 공개되었다는 intraday 증거를 제공하지 않습니다. 따라서 이
조회 결과만으로 `missing_nav_timestamps` 또는 FX PIT gate를 해제하지 않습니다.
FRED를 쓰려면 동일 frozen run을 새로 수집하고, 보수적 availability 정책을 적용한
별도 candidate로 readiness를 다시 진단해야 합니다. 기존 canonical artifact와
historical metrics는 변경하지 않았습니다.
