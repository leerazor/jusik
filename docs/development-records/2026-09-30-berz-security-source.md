# BERZ 상품 유형 원문과 TNMG 가격 기준 감사

- 작업 `berz-security-source-20260930`; 기준 `42b0e4b`. 생산 코드·정책·캐시·준비 자료는 변경하지 않았다.
- [SEC 424B2 원문](https://www.sec.gov/Archives/edgar/data/927971/000121465925015794/i113255424b2.htm)을 고정 URL로 GET 1회 조회했다. [조회 receipt](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/result.json), [원문 평가](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/assessment.json), 보존 원문 SHA `8a74ed1fe28f9af04026f7f75e8b9a796e7cf42f3c03834bf7812b77b6d06976`을 결속했다. 원문은 BERZ를 NYSE 상장 역레버리지 ETN 및 Bank of Montreal 채무증권과 직접 연결한다.
- 제출일은 2025-11-03, SEC 접수 기록은 `2025-11-03T22:29:59Z`다. 접수 시각을 최초 공개 가능 시각으로 간주하지 않는다. 평가 시작 2025-09-11보다 늦은 원문이므로 당시 상품 유형·선정의 시점 적격성은 입증되지 않았다. 기존 분류나 과거 선정은 소급 수정하지 않는다.
- [TNMG 오프라인 대사](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/tnmg-basis-result.json)는 보존 원문 SHA `6438e2405b2be3b1574af1332a2b3ea8bb0d4a629da7bb27b0f6ba7c7c6e288f`에서 2025-12-23 `1:20`, 2026-09-08 `1:8` 분할을 확인했다. 9월 8일 OHLCV 전부 null이고 인접 유효 종가 및 adjclose를 함께 기록했다. 원문에는 quote가 raw인지 명시한 필드가 없다. 가격 비율이나 adjclose 일치로 이를 추정할 수 없어 `price_basis=unknown`, `BLOCKED_PRICE_BASIS_UNKNOWN`이다. 기존 [회계 계약](../../backend/jusik/market_history_action_accounting.py)은 raw 가격을 요구하므로 분할 이중 적용 위험을 배제하지 못한다. 사건 관측시각도 미확인이다.
- 검증: SEC sentinel 선기록·GET 1회·재시도/리다이렉트/검색 0, 보호 원본 5개 SHA 일치. TNMG 네트워크·수집기·회계/NAV·금융 실험 0회. 두 audit 스크립트 Ruff와 strict mypy 통과; 기존 생산 코드와 테스트가 불변이므로 전체 테스트는 재실행하지 않았다. 별도 결속은 [verification](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/verification.json)에 남겼다. 추가 결제·주문·push 없음.
- 재개: BERZ 평가 당시 상품 유형과 공개 가능 시점을 입증하는 동시대 원문, TNMG 해당 역사 시점의 명시적 quote 가격 기준 및 사건 관측 근거를 독립 범위에서 확보해야 한다. 이번 증거는 연구 입력·성과 적격으로 승격하지 않는다.
- workflow 판단: 고정 URL 1회와 기존 원문 오프라인 대사로 두 차단 조건을 분리했다.
- 근거: 실제 외부 GET 1회, TNMG 네트워크 0회이며 시간·비용 절감 비교치는 측정하지 않았다.
- 다음 조정: 같은 원문 재조회나 가격 변동 역산을 반복하지 않고 새로운 시점·가격 기준 증거가 있을 때만 재검토한다.

## 완료와 남은 조건

- 증거 작업 완료, 투자 검증 미완료. 구현 `f926ae2`, main 통합 `e5499edec2338acaaa7c13657e9a4baf0f720f4b`. 독립 최종 review와 통합 결속 PASS: audit9·문서2·보호5 SHA, backend tree 불변, 로컬 링크9 확인. 상세는 audit `final-review.json`·`integration.json`에 보존했다.
- 최종 검토에서 동명 문서 basename 키가 개발기록 SHA를 누락하는 결속 오류를 발견했다. 정확한 저장소 상대경로 두 개로 교정했고 원문·조회·검사 스크립트는 재실행하지 않았다. 후속 manifest는 경로를 키로 사용한다.
- 기존 요청 결손22의 40419·빈 응답 AVNS1·상품 종류 불일치 BERZ/FNGS2는 **2026-09-22 보존 receipt 기준** 분류다. [시도별 후속 대사](2026-10-01-us-gap-provenance.md)는 AVNS가 2026-09-30 재요청에서는 404였음을 별도로 보존한다. 어느 응답도 상장폐지 원인을 확정하지 않는다. BERZ의 후일 ETN 근거는 확보했지만 평가 당시 선정 적격성 근거는 추가로 필요하다. TNMG는 이22와 별도로 캐시에 복구됐으나 가격1일·분할 관측시각·가격기준 문제가 남는다.
- 실행기 상태를 새로 조회했을 때 paused=false였으므로 수동 작업 전에 pause했다. running0, service/timer inactive. 이 상태를 유지했고 사용자 루트 HANDOFF와 기존 캐시142를 보존했다. 환경·ignored경로는 audit에 저장한 후 작업 워크트리·브랜치를 정리했다.
- 다음 작업: 자료 제공자가 명시한 TNMG 기간별 가격기준/분할 조정 규칙과 해당 원문을 확보할 수 있는지 제한된 source scope부터 판단한다. 현재 가격 비율 역산·동일 SEC 문서 재조회·동일 해시 검사 반복은 하지 않는다. 배당·수수료·FX·NAV 전체 인수 검증과 비용 포함 비교는 계속 미완료다.
