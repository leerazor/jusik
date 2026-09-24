# R1-05 secret-free provider request identity

- 구현: collector cache manifest의 신규 `request_descriptor` 필드에 API 비밀키를 제거한 canonical source/URL/method/params/data JSON을 보존합니다. 기존 manifest는 optional field 기본값으로 읽어 호환성을 유지합니다.
- 검증: `backend/tests/test_market_data_collector.py` 146 passed, Ruff check, strict mypy passed. 전체 Ruff format check는 기존 파일의 unrelated formatting 차이로만 실패해 대량 정리는 하지 않았습니다.
- fresh receipt: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-cache-0945/manifest.json` (SHA `146895215dd4b649980cd132d820f02107397939ef0b1bb54c1f520056624061`), 모든 137 entries에 descriptor가 존재합니다. source counts는 Alpha Vantage 2, Yahoo 76, FRED 59입니다.
- 결과: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-result-0945.json` (SHA `a42fd8b4f53f1f05f39637dcff34806fa0fad17de6ad467acc40e0ae2a11ed7f`)의 coverage는 여전히 `27472/20306`, missing `7166`입니다. 따라서 R1-05와 경제 acceptance는 미승격합니다.
