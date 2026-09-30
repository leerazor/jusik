# Yahoo 가격 기준 자료 인계

- [개발 기록](../development-records/2026-09-30-yahoo-price-basis-source.md), [판정](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/result.json), [검증 결속](/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/verification.json)이 진입점이다. 구현 `a199ca6`, main `60bdf34ff486824f035a206be33b4c9d4629b783`; 독립 review·main 결속 PASS, 워크트리·브랜치 정리 완료.
- Yahoo Help 검색 1회에서 선택한 URL의 본문 open 1회가 429로 실패했다. 검색 발췌는 본문 근거가 아니며 chart JSON `quote`의 raw/adjusted 의미를 확인하지 못했다. TNMG price basis unknown, 연구 입력·성과 적격 false를 유지한다.
- 다음에는 공식 본문과 chart JSON 필드 적용 근거를 새 범위로 확보할 수 있을 때만 재개한다. 같은 조건에서 시간 경과만을 근거로 동일 URL 재시도, 시세 재조회, 캐시142 수정, 분할 회계·NAV·성과 계산은 하지 않는다.

- [이전 BERZ·TNMG 증거](2026-09-30-berz-security-source.md)와 캐시142를 재사용한다. FX272 동일 입력 검증·원문6행 대사·동일 URL·가격 조회는 반복하지 않는다. 자동 raw 승격 결함도 발견되지 않았다. 다른 즉시 작업을 찾지 못한 근거는 audit `alternatives.json`에 있다.
- 다음 heartbeat: Git·작업 소유권·실제 runner 상태와 새 증거 identity를 먼저 확인한다. runner가 READY 작업을 실행하면 수동 writer를 만들지 않는다. 상태 변화가 없다면 조용히 종료하고 실패 LLM/외부 호출을 반복하지 않는다. 새 source evidence나 최소 재현/수리 근거가 생기면 해당 단일 범위만 재검토한다.
- 수동 종료 뒤 runner 재개·timer·실제 cycle 결과는 `/home/kwl/.local/share/jusik/portfolio-audit/20260930-yahoo-price-basis-source/runner-resume.json`에서 확인한다. 기록된 과거 상태를 현재 실행 중이라고 해석하지 않는다.
