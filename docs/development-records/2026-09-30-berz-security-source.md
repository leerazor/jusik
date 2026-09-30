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
