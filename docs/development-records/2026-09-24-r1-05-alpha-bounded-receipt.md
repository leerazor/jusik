# 2026-09-24 R1-05 bounded Alpha Vantage fallback receipt

Yahoo 부분 이력 LIME/MDA의 대체 provider 가능성을 확인하기 위해 Alpha Vantage `TIME_SERIES_DAILY`를 두 심볼에 한정해 요청했다. 원문과 manifest는 다음 durable 경로에 보존했다.

`/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/alpha-lime-mda-bounded/`

두 응답 모두 HTTP 200이었지만 free key에서 `outputsize=full`은 premium 기능이라는 provider 안내만 반환했고 일봉 행은 0개였다. 두 raw response의 SHA-256은 동일한 `37aaccd80b9e6babd46c5275fa4692477b19eb2354b0773e78c8c473b7a87e5f`이며 manifest SHA-256은 `9a503b14902fd54cda02e4897308a2625c59e01482a609a6e2033ffc8be8d6f7`이다.

이 receipt는 Alpha Vantage 무료 fallback이 LIME/MDA의 historical coverage를 보강하지 못했다는 근거다. Yahoo의 366개 누락을 제외하거나 PIT/경제 acceptance로 승격하지 않으며, 유료 provider 신청이나 다른 원천 자료가 생기기 전 R1-05는 보수적으로 대기한다. 실거래·PAPER/live·원격 변경은 없다.
