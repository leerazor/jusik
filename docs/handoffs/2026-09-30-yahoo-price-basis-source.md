# Yahoo 가격 기준 자료 인계

- [개발 기록](../development-records/2026-09-30-yahoo-price-basis-source.md), [판정](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/result.json), [검증 결속](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/verification.json)이 진입점이다. 구현 커밋의 main 통합은 감독자 예정.
- Yahoo Help 검색 1회에서 선택한 URL의 본문 open 1회가 429로 실패했다. 검색 발췌는 본문 근거가 아니며 chart JSON `quote`의 raw/adjusted 의미를 확인하지 못했다. TNMG price basis unknown, 연구 입력·성과 적격 false를 유지한다.
- 다음에는 공식 본문과 chart JSON 필드 적용 근거를 새 범위로 확보할 수 있을 때만 재개한다. 동일 URL 즉시 재시도, 시세 재조회, 캐시142 수정, 분할 회계·NAV·성과 계산은 하지 않는다.
