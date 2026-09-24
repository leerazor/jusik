# 2026-09-24 R1-05 explicit-exclusion coverage accounting

## 발견

fresh US receipt의 `missing_sessions=7166`에는 request-excluded 25개 심볼의 6,800개 세션이 포함되어 있었다. 이 심볼들은 원인·request identity와 함께 명시적으로 제외된 것이므로 eligible coverage의 missing으로 다시 세면 안 된다. 실제 비제외 누락은 LIME 221개와 MDA 145개이며, 이 부분 이력은 그대로 차단한다.

## 변경

`market_data_collector.py`의 US diagnostics에서 `request_excluded` 심볼은 `expected_sessions=0`, `missing_sessions=0`으로 집계하고 제외 목록·원인은 별도로 유지한다. 비제외 심볼의 partial history 진단은 기존대로 유지한다. 회귀 테스트에서 excluded coverage를 확인한다.

추가로 심볼별 `first_observed_session`을 진단에 보존한다. 이는 provider 응답에서 실제로 관측된 첫 거래 세션일 뿐이며 historical publication/observed_at 또는 상장·상폐 원인을 의미하지 않는다. 따라서 LIME(2026-07-01)와 MDA(2026-03-12)의 366개 누락을 자동 제외하거나 PIT 근거로 승격하지 않는다.

## 검증

- collector pytest: 146 passed
- Ruff check: passed
- strict mypy: passed
- symbol diagnostic first-observation regression: passed
- Ruff format 전체 check는 파일의 기존 unrelated formatting 차이로 실패했으며 대량 포맷은 하지 않았다.

## 판정

이 변경은 coverage 계산의 중복 집계만 교정한다. LIME/MDA 366개 실제 누락, 전체 PIT completeness, R1-05 checkbox와 경제 acceptance는 여전히 미승격이다.

수정된 collector로 기존 `fresh-cache-0945`를 재사용해 새 결과를 생성했다. 결과 `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-result-1010.json`의 SHA-256은 `b659c38676d531b70c3ea172fdcb5e2680bd4eb0ec6a1f2a2f9f913ba50c5d0e`이며 coverage는 `20672/20306`, missing `366`이다. 새 네트워크 수집은 하지 않았다.
