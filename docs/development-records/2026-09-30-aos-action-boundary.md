# AOS 배당 회계 날짜 경계 오프라인 확인

- 상태: 단일 날짜 변환 feasibility receipt 완료; pilot 정책·자료·성과 적격은 미승인
- 기록 시각: 2026-09-30T09:23:01.040248+00:00
- 작업 slug: `aos-action-boundary-20260930`
- 기준/통합: `d73d37a6a730bd885201a155e01448f227188eec` / 감독자 확정 예정
- 범위: AOS source-reported 배당락일 2025-10-31과 지급일 2025-11-17 두 날짜의 경계만 오프라인 1회 계산. 생산 코드·원본·준비 자료·정책 변경 없음

## 변환과 근거

- [감사 스크립트](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-action-boundary/derive_boundary.py)는 기존 `MarketCalendar.lookup`을 직접 호출했다. AOS [원문 identity](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-source/identity.json)의 NYQ와 prepared instrument의 NYS가 모두 XNYS·`America/New_York`에 매핑되고, 배당락일은 실제 calendar session으로 조회됐다. `2025-10-31 09:30 EDT` → **`2025-10-31T13:30:00Z`** (UTC−04:00).
- `research_dividend_overlay.py:365-367`의 지급 규칙은 전체 simulation 안에 있어 독립 helper로 직접 호출할 수 없다. 감사 스크립트는 source SHA와 원문 표현을 확인한 뒤 `payment_date + 1 local day`의 자정식만 최소 복제했다. `2025-11-18 00:00 EST` → **`2025-11-18T05:00:00Z`** (UTC−05:00). 이는 원본 overlay 전체 호출 결과가 아닌 **회계 정책 파생 후보**다.
- [receipt](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-action-boundary/receipt.json) SHA `36ed63427c58bc4943dbafe2f3d9c7bfde6d46c1831a8d62acbd212740bb154f`에 스크립트 SHA `37899ef178ef221bb88d50589158d10c377208849201e7cbeed9b3720fb00489`, calendar artifact SHA `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8`, scope·입력 SHA와 결과를 결속했다. 보호 파일 19개·관련 source 4개 SHA 일치.
- [이전 날짜 근거](2026-09-30-aos-event-evidence.md)의 배당락일은 발행사 호스트 검색 스니펫 대상 행에만 있으며 역사 표 제공자는 Mergent다. 원문 open에는 그 행이 없었다. Yahoo occurrence의 `13:30Z`와 이번 거래소 open이 같아도 사건 역할이나 장중 효력을 입증하지 않는다. 배포본 `2025-10-13 17:54 ET`의 분 단위 표기는 별도이며 공급자 `observed_at`·`available_at`은 null이다.

## 검증·영향·재개

- `Python 3.13 ast.parse/compile` 통과 후 `PYTHONPATH=backend python3.13 derive_boundary.py`를 1회 실행했다. 결속·DST·보호 SHA 검증 PASS. `derived_policy_candidate=true`, `pilot_policy_adopted=false`, `research_input=false`, `performance_eligible=false`. 보유량·entitlement·action·receivable·ledger·수익률은 생성하지 않았다. 네트워크·금융 실험·주문·PAPER·배포·push·서비스 변경 0회.
- 기능·API·설정·생산 데이터 계약을 바꾸지 않아 기능 문서는 수정하지 않았다. 코드 변경이 없으므로 기존 247개 테스트는 재실행하지 않았다. 다음은 같은 날짜 변환·출처 조회를 반복하지 않고, 공급자 관측·역사 버전과 실제 배당 자격/보유 replay·raw 가격 기준 및 사전 비용 정책 근거를 별도 scope에서 확인하는 것이다.
- workflow 판단: 도움 됨 — 기존 calendar를 직접 사용하고 overlay 지급 규칙의 최소 식만 격리해 전체 simulation 실행을 피했다.
- 근거: 단일 변환 1회, 보호 19개·source 4개 해시와 DST 기대값 일치. 시간·호출 절감의 비교값은 미측정이다.
- 다음 조정: 유지 — 파생 시각은 정책 후보로만 보존하고 새 원천·회계 조건이 확보된 후에만 pilot 연결을 심사한다.
