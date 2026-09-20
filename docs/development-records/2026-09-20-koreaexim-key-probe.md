# KoreaExim API key bounded probe

- 상태: 원천 응답 확보·PIT application 차단 유지
- 기록 시각: 2026-09-20T08:30:00Z
- 작업 slug: `koreaexim-key-probe-20260920`
- 기준/통합: `53c9787` / 다음 통합 커밋
- 범위: `.env`의 KoreaExim 키가 실제 API 인증과 USD row 응답에 사용되는지 한 날짜만 bounded 확인했습니다. FX/NAV/Sharpe/readiness에는 연결하지 않았습니다.

## 결과

- 요청 날짜: `2026-09-18`
- HTTP/응답: 정상, 23 rows, USD row 1개, USD rate field 존재
- response SHA-256: `d5188e57510fba1b15c685ce8793ca6cf08bdf277c6cf90a68538a660a0145b3`
- USD row에 publication/availability/date/time 필드: 없음
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-koreaexim-key-probe/`

## 결정

- API key와 transport/parser는 작동하지만 row별 historical availability 또는 publication instant를 증명하지 못합니다.
- 다음 UTC 자정 policy bound를 실제 publication 사실로 승격하지 않습니다.
- 따라서 R2-03 FX application, 원화 NAV, Sharpe, readiness 상태는 변경하지 않습니다.

## 검증·안전

- bounded live probe 1회, 임시 cache와 audit raw/probe manifest 보존
- 키 값은 출력·문서·Git에 기록하지 않았습니다.
- 실제 주문·PAPER/live 승격·remote push·Windows 종료 없음. runner paused/service inactive/timer disabled 유지.

## 재개 조건

- KoreaExim 응답의 publication/availability timestamp 계약과 historical cutoff 적용 정책을 별도 근거로 확보하거나, 승인된 대체 FX 원천을 선택해야 합니다.
