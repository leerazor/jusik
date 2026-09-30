# AOS 사건 관측·배당 회계 입력 계약 감사

- 상태: 계약 결손 기록 완료; 자료·PIT·성과 적격은 차단 유지
- 기록 시각: 2026-09-30T08:22:13.009839+00:00
- 작업 slug: `event-observation-contract-20260930`
- 기준/통합: `86eef581b0f94bee0980b6709e7d95dbdd0861fa` / `cfd57f1061eae349289ac8c278e97e32649dc29c`
- 범위: 기존 AOS 1건 근거와 현재 코드의 소비 경로만 대조. 생산 코드·준비 자료·정책·원본·수집 상태 변경 없음

## 필드 계약과 결정

[감사 matrix.json](/home/kwl/.local/share/jusik/portfolio-audit/20260930-event-observation-contract/matrix.json)은 9개 행마다 필드, 현재 근거, 미확인 사항, 소비 함수, 해소 조건을 명시한다. 핵심 구분은 다음과 같다.

| 분류 | 현재 근거 | 필요한 확인과 연결 |
| --- | --- | --- |
| 원천 사건·공표 | AOS 원문 배당 USD 0.36, Yahoo occurrence `2025-10-31T13:30Z`; 발행사 기준일 10-31·지급일 11-17, 연결 배포본 `2025-10-13 17:54 ET`(EDT 기준 21:54 UTC, 분 단위) | Yahoo 날짜의 역할과 배당락·자격 경계, 사건별 공급자 관측/과거 공개 가능성·출처 버전 연결은 미확인. 게시 분을 `:00`초 사실이나 Yahoo `observed_at`으로 채우지 않는다. |
| 코드의 시각 검사 | `ApproximateEvent`는 timezone-aware 시각을 받고, 두 시각 중 늦은 값을 cutoff에 적용하며 unknown을 차단한다. `captured_at`은 별도 수집 시각이다. | 현재 모델에 원문 분 정밀도 표현이 없다. 초 단위 증거가 모든 회계에 필수라는 뜻은 아니며, 분/불확실 구간의 보수적 표현을 별도 격리 계약으로 검토한다. 과거 **우리 시스템 최초 수집 영수증**을 일률적 필수조건으로 새로 만들지 않는다. |
| 원천 경제 조건 | 금액은 원문·발행사 자료에서 일치한다. 기준일·지급일은 알지만 배당락일과 effective 경계는 미확인이다. | `ApproximateEvent`는 금액·통화·날짜 역할을 보존하지 않고, `CorporateAction`은 배당을 지원하지 않는다. 원문 identity와 유효 날짜·통화·raw 가격 기준을 입증해야 한다. |
| 파생 회계 입력 | 기존 `DividendAction`과 `accrue_dividend`/`pay_dividend`는 확정 배당 자격의 gross receivable과 현금 이동을 수행한다. | `entitled_quantity`는 공급자 필수가 아니라 검증된 ex/effective 시점의 replay 포지션에서 산출한다. `actions=()`·`actions_complete=false`·`dividends_excluded`인 현 근사 자료를 곧바로 NAV에 넣지 않는다. |
| 사전 정책 | 기존 후향 overlay는 현재 revision 기반 세전 계산이며 PIT·비용 입력이 아니다. | 새 pilot의 세금·FX·거래/환전 비용 및 지급일 회계 경계는 독립 범위에서 사전 고정해야 한다. 이 감사는 adapter·비용/NAV 실행을 승인하지 않는다. |

코드 근거는 `backend/jusik/market_history_approximate.py:126,942,1099`, `market_history_models.py:135`, `market_history_action_accounting.py:196,630,730`, `research_alpha_actions.py:201`, `research_dividend_overlay.py:42` 및 [현행 사건 계약](../market-research.md#미국-사건-시각-불변성-계약-r1-02)이다. Alpha의 현재 응답 수신시각도 과거 공급자 관측시각으로 대입할 수 없다.

## 검증·영향·재개

- [audit result.json](/home/kwl/.local/share/jusik/portfolio-audit/20260930-event-observation-contract/result.json)에 matrix SHA `3164bc2ee209cea6b51f9b598b2a2c87e3522c00283cefc9475eff80773a5094`, AOS assessment SHA `5f335ef83d0ceb841a6dff14f57b381df5372a3bed6efb0ebfb327f8f73d2b14`, backend tree `36c35a0d52f43d312e0cf7d3a891b009b3e822c7`을 결속했다. 기준 source 6개 해시·AOS raw/prepared·cache140 manifest 일치 확인. 외부 조회·금융 실험·주문·배포·push·서비스 변경 0회.
- 사용자 기능·API·설정·데이터 계약을 바꾸지 않았으므로 생산 기능 문서는 수정하지 않았다. 기존 247개 테스트도 코드 불변이라 반복하지 않았다.
- 다음 독립 범위의 첫 단계는 **현재 근거가 요구하는 최소 원천 필드와 날짜/시각 정밀도 표현**을 격리 계약으로 검토하는 것이다. 그 계약과 replay/비용 정책이 확인될 때만 기존 순수 회계 함수를 연결할 adapter 범위를 심사한다. 125건 재수집이나 후향 overlay 이식은 이번 승인 범위가 아니다.
- workflow 판단: 도움 됨 — 확정된 scope와 기존 코드·AOS 근거를 재사용해 필수 원천, 파생 입력, 사전 정책을 분리했다.
- 근거: 새 네트워크·수집·테스트 반복 0회, 기준 source 해시 6개와 증거 결속 PASS. 시간·호출 절감의 비교 측정은 하지 않았다.
- 다음 조정: 유지 — 필드 계약이 증명되기 전 구현과 대량 조회를 열지 않고, 좁은 독립 범위에서 표현 가능성부터 판단한다.

## 통합과 정리

- 구현 `584f057b7244801406cc5f9722cd9d28066143c8`; 독립 review는 계약 감사에 한해 PASS. main 통합 후 전체 backend·기준6파일·추가회계/overlay2파일·AOS근거 불변 및 matrix/scope 결속 PASS. `review-final.json`, `integration.json`, `routing-code-review.json`에 결과를 보존했다.
- 원문·prepared·캐시140 검사는 변경 없는 worker 검증을 재사용했다. 환경·audit 보존 후 깨끗한 전용 worktree/branch를 정리했다. 루트 사용자 HANDOFF와 다른 작업은 보존했고 runner paused/inactive, 주문·PAPER·결제·권한·credential·push 변경 없음.
- 원천 사건125개 관측시각 결손과 기존24 시세 실패는 그대로다. 이번 완료는 왜 비용 포함 배당 NAV 비교를 아직 실행할 수 없는지와 다음 연결 조건을 명확히 한 결과다.
