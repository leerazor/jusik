# 미국 우선주 상품명 분류 보정

- 상태: 구현 완료, 독립 검토·main 통합 대기
- 기록 시각: 2026-09-30T06:25:21Z
- 작업 slug: `us-preferred-classification-20260930`
- 기준/통합: `584df86c5daa1a8506e5c8f3fba86da1cbb7ec9d` / 감독자 확정 예정
- 범위: Alpha Vantage `PRF PERPETUAL` 연속 상품명과 신규 미국 수집 v3 계약·완료 증거. 전략·수익률·NAV·원본 재수집 없음.

## 변경과 결정

- 기존 cache 상품명 `Metlife Inc 4.75 PRF PERPETUAL USD 25 11000th int Ser F`가 `Stock`으로 분류되어 ordinary가 되던 오류를 재현했다. `\bprf\s+perpetual\b`만 `OTHER`로 추가했다. 단독 단어, 다른 중간 단어, `PRFX`, 티커 형태만으로는 제외하지 않는다. 공식 제품 근거는 audit `preferred-source-notes.json`이다.
- 신규 collector 출력은 `approx-us-r1-event-timing-v3`, 별도 pool hash와 `completed-us-exclusions-v2.json`을 쓴다. 기존 v2 정규화·pool hash·`completed-us-exclusions-v1.json`·prepared 파일은 보존한다. 직접 완료 기록/조회 호출의 기본은 v2이며, 출력 검증은 파일 안의 정규화 버전으로 marker를 선택한다.
- 기존 `data_contract_hash` 계산은 수정하지 않았다. 정규화 버전과 pool hash가 입력에 포함되어 v2 pilot과 v3 final을 구분한다. 미지원 미국 정규화 버전은 읽기·완료 검증에서 거부한다.
- 독립 review에서 v2 자료의 정규화 문자열만 v3로 바꾸면 `PRF PERPETUAL` 이름을 가진 universe가 v3 reader와 완료 검증을 통과하는 오류를 확인했다. 공통 이름 판정 함수를 parser·reader·완료 검증에 적용해 v3에서 거부한다. v2 reader·marker 수용은 회귀로 보존했다.

## 문서·계약 영향

- 사용자 계약: [시장 연구](../market-research.md), [현행 연구 조건](../research-mandate.md), [투자 로드맵](../investment-development-roadmap.md)의 새 수집 설명을 v3로 갱신했다.
- mandate JSON·투자 조건·LIME/MDA 정책·`market_history_sources.py`·기존 raw/cache/result는 수정하지 않았다. `market-research-mandate.sha256`은 변경한 Markdown 두 문서의 SHA 행만 동기화했다. JSON·legacy·governance·US 정책 네 행은 불변이다. v3 기능은 새 출력 경로에서만 사용한다.

## 검증

- `pytest -q` (시장 연구 3개 파일 + runner governance 3개 focused 사례) — 247개 통과. 상품명 경계, v2/v3 marker 공존·출력 hash, legacy pool golden hash, 미지원 버전, pilot/final 계약 불일치와 mandate 정책 필드를 확인했다.
- review 재현 회귀 2개는 수정 전 실패, 공통 판정 적용 후 통과했다. 최종 focused 전체 검사도 통과했다.
- `ruff check`와 `ruff format --check` — 해당 소스·테스트 검사. `mypy --strict --follow-imports=silent` — 변경된 소스 2개 통과. 테스트 전체 strict mypy에는 기존 테스트의 다수 타입 오류가 있어 생산 소스만 type gate로 사용했다.
- audit `baseline.json`의 mandate JSON·계약 소스·기존 v2 prepared(`c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`)·결손 기록·v2 marker·cache manifest 6개 SHA 일치. 사건 표본 원문 3개도 `event-observation-blocker.json` 기록 SHA와 일치.
- `validate_mandate`와 `validate_dispatch_gate` 통과. manifest에서 Markdown 두 행 외 네 행 불변을 diff로 확인했다.
- 추가 runner focused 검사의 `test_tracked_research_mandate_preserves_authoritative_fields` 1개는 현재 JSON의 기존 `new_us_research_policy`를 기대값에서 누락해 실패했다. 감독자가 기준 main에서도 동일 실패를 재현하고 이 한 함수 수정 범위를 승인했다. JSON의 5개 필드를 정확히 검증하도록 보완했다. 정책 값과 생산 코드는 불변이다.
- 시장 네트워크·새 v3 실수집·전략·NAV·성과·주문 검사 0회. 기능 회귀에 필요한 local mock/fixture만 사용했다.

## 안전·운영 상태

- 서비스·runner·실거래·PAPER·배포·원격 push·credential은 변경하지 않았다. 기존 자료의 요청 제외 25심볼과 사건 125행 관측시각 결손은 해결되지 않았다. 기술 구현을 자료 인수 또는 투자 성과로 해석하지 않는다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-preferred-classification/` (`baseline.json`, `legacy-contract-hashes.json`, `event-observation-blocker.json`). 기존 prepared와 작업 cache는 `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/`에 보존.
- 새 수집 전에 기존 cache만으로 v3 선정·miss 변화를 오프라인 계산해 범위를 고정한다. 동일 Yahoo 요청은 새 증거 없이 반복하지 않는다. 사건 관측시각은 시세 재조회나 fetch 시각 치환으로 해결할 수 없으며 종목·사건별 역사 관측시각 원본 근거가 필요하다. 접근·비용은 미확인이다.
