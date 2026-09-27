# Alpha Vantage 자료 출처 후보 검토

- 상태: 완료 (공개 공식 문서 기반 권고 보완; 실제 자료 검증은 미실행)
- 기록 시각: 2026-09-27T05:38:29Z
- 작업 slug: `portfolio-held-band-alpha-vantage-source-evidence`
- 기준/통합: `a54a47b24571995e9204a3eab67eef976bc5058e` / `8ad78df52d8dd63438bca98ab234af8f621f5fab`
- 범위: Alpha Vantage의 날짜별 US listing status, 시세/조정 이력 범위, rate limit, 현재 Terms의 개인·비상업 연구 범위를 공개 official docs에서 확인해 held-band 자료 출처 권고에 반영했습니다. mandate·agent 역할·투자 기준·v2 초안/JSON·코드·cache는 변경하지 않았습니다.

## 변경과 결정

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)에 Alpha Vantage 후보 분석을 추가했습니다. `LISTING_STATUS`는 현재 또는 2010-01-01 이후 특정일의 US stock/ETF active/delisted 목록을 반환하고 key를 요구합니다. Daily raw는 25년 이상을 설명하지만 free `compact`는 최근 100 data points, `full`은 premium입니다. Daily adjusted 및 split/dividend history도 25년 이상을 표방하지만 premium endpoint이며, 일반 free use는 25 requests/day입니다.
- Terms는 개인·비상업 사용과 private individual 성격의 투자분석·연구·테스트를 허용 예시로 제시합니다. 그 범위를 넘는 목적, 법인·단체 대리, 제3자 정보 이용, 특정 금융기관 소속/affiliate는 commercial use 조건에 해당합니다. 실제 사용자의 eligibility는 확인하지 않았습니다. Premium 가격도 정적 공개 페이지에서 확인하지 않았습니다.
- 날짜별 membership은 US universe 조사 우선 후보로 남기되, publication/observation/receipt timestamp, 수정 버전, 전체 과거 universe completeness를 보장한다고 주장하지 않습니다. 실시간/과거 API 호출을 하지 않아 source를 최종 허용하거나 strict PIT로 평가하지 않았습니다.
- provisional 근거·범위·해제 조건은 [작업 등록부](../worktree-tasks.md) 및 source 평가 subsection에 기록했습니다. Free/premium endpoint 의미로 schema/fixture를 준비하는 것은 reversible이며, 실제 사용 전 account/credential, 사용 목적·Terms 적격성, PIT data checks와 승인된 최종 data acceptance를 대조합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. UI/API 동작 변화 없음.
- 운영 문서: 작업 등록부 및 current handoff 갱신.
- API·설정·데이터 계약: 변경 없음. provider API를 호출하거나 응답 자료를 저장하지 않았습니다.

## 검증

- `git diff --check` — 통과.
- mandate SHA-256 — `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1` 동일.
- v2 JSON — 미결 값 20개 모두 `null`; `registered`, `approved`, `execution_allowed` 모두 `false`.
- 문서 조사: [API documentation](https://www.alphavantage.co/documentation/), [support & API limits](https://www.alphavantage.co/support/), [Terms of Service](https://www.alphavantage.co/terms_of_service/), [Premium API](https://www.alphavantage.co/premium/).
- 문서만 바꿨으므로 pytest/Ruff/typecheck를 실행하지 않았습니다. 실제 data coverage, market performance, PIT eligibility는 검증하지 않았습니다.

## 안전·운영 상태

- API key 발급·접근, account 생성, data/API request, price/subscription purchase, external service change, DB/cache write, PAPER/live mutation, broker order, remote push는 없었습니다.
- 실제 API 응답 검증은 key 미제공 및 개인 사용 자격·의도 미확인으로 blocked입니다. 이는 공개 문서 조사·offline schema/test를 막지 않습니다. Premium full-history purchase는 실제 비용 승인이 있어야 합니다.

## 증거와 재개

- audit: 없음. 다운로드 또는 원시 market data를 생성하지 않았습니다.
- 남은 작업·차단 조건: 후보 source를 final allowlist로 고정하거나 strict PIT/data acceptance로 승인하려면 timestamped publication/availability 및 수정 버전, 과거 membership coverage, corporate actions와 FX 결합 품질을 검증해야 합니다. 정식 preregistration 및 OOS는 v2 미결 필드, 승인된 freeze, 적격 미노출 미래자료가 충족될 때까지 각각 pending/blocked입니다.
- 다음 시작: 새 자료를 당기지 않고 기존 US approximate cache와 readiness report를 읽기 전용으로 대조해 종목별 기간·bar 결손·identity/action/FX 진단이 어떤 offline fixture 범위를 지지하는지 기술적으로 요약합니다. 결과는 개발/회귀 용도 한정입니다.
