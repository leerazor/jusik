# Massive 자료 출처 후보 검토

- 상태: 완료 (공개 문서 기반 후보 평가; 실제 자료 적격성 검증은 미완료)
- 기록 시각: 2026-09-27T05:30:02Z
- 작업 slug: `portfolio-held-band-massive-source-evidence`
- 기준/통합: `b9c8cdc7c673b680c6e583cf6c762ca817216d6d` / `41be8c2d518eabf02d0e6f5517e2deb3d10ba869`
- 범위: Massive US stocks 공개 공식 문서의 요금, 과거 ticker/reference 및 ticker-change 이벤트, PIT 증명 한계, 사용권을 조사해 자료 출처 권고에 기록했습니다. 기존 mandate, agent 역할·orchestration, v2 preregistration, 코드·테스트, 자료 cache와 투자 기준은 변경하지 않았습니다.

## 변경과 결정

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)의 자료 출처 절에 Massive 후보 평가를 추가했습니다. 확인된 무료 Basic 범위(2년·EOD·분당 5회), $29/5년·$79/10년·$199/20년 이상 개인 요금제, `active=false` 참조, ticker-change 이벤트의 날짜 필드와 이력 범위를 기재했습니다.
- 특정 날짜의 reference 조회·delisted ticker·이벤트 연결은 과거 symbol 상태와 identity 조사에 유용하지만, 당시 관측 가능 시점, 수정 이력, 전체 과거 universe를 문서만으로 입증하지 않습니다. Vendor의 survivorship-bias claim을 strict PIT 증거로 간주하지 않습니다.
- 공식 Market Data Terms는 개인·비사업·비상업 용도 제한뿐 아니라 별도 허가 없는 non-display 및 데이터 기반 투자전략 파생물 작성을 제한합니다. 따라서 Massive를 현 연구/백테스트 자료원으로 채택하지 않고, 공개 interface 설명을 source-agnostic schema 조사 참고에 한해 provisional로 둡니다. 유료 plan이 이 사용 제한을 해소한다고 확인되지 않았습니다.
- 추가 적용 가정의 근거·범위·해제 조건은 [작업 등록부](../worktree-tasks.md)의 provisional assumption 및 결정 문서 후보 절에 남겼습니다. 계약상 사용 허가, 시간화된 publication/availability와 revision provenance, universe coverage, 기업행동 범위가 독립적으로 확인돼도 최종 source acceptance와 preregistration freeze 전까지 OOS 사용은 허용되지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 공개 문서 평가이며 사용자-facing API/화면 동작은 바뀌지 않습니다.
- 운영 문서: 작업 등록부와 현재 handoff에 조사 완료·차단·다음 runnable 상태를 기록합니다.
- API·설정·데이터 계약: 변경 없음. vendor API 요청과 실제 dataset 사용은 하지 않았습니다.

## 검증

- `git diff --check` — 통과.
- mandate SHA-256 재확인 — `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1` 동일.
- `portfolio-held-band-preregistration-draft-v2.json` — 미결 20개 값 모두 `null`; `registered`, `approved`, `execution_allowed` 모두 `false`.
- 공식 출처와 문서 변경 대조: [가격표](https://massive.com/pricing), [Stocks REST endpoint overview](https://www.massive.com/docs/rest/stocks/overview), [Ticker Events](https://www.massive.com/docs/rest/stocks/corporate-actions/ticker-events), [ticker-change 설명](https://massive.com/knowledge-base/article/how-does-massive-handle-ticker-changes-and-acquisitions), [Market Data Terms](https://massive.com/legal/market-data-terms-of-service).
- 변경은 문서 1개뿐이므로 pytest, lint, typecheck는 실행하지 않았습니다. 별도 분석 성과나 데이터 quality pass를 주장하지 않습니다.

## 안전·운영 상태

- 공개 official docs를 열람했으나 API key 발급/접근, vendor account 생성, stock data API 호출·다운로드·캐시 변경, 실제 비용, 주문, DB/PAPER/live 변경, 원격 push는 없었습니다.
- 실제 API 자료 조사 task는 적절한 credential 및 전략 연구를 허용하는 계약/권한이 없어 해당 부분만 blocked입니다. 유료 plan/license는 비용 승인 전에 구매하지 않습니다.
- 수동 문서 수정 중 roadmap runner를 임시 pause했고 one-shot service를 stop했습니다. 작업 후 원래 `paused=false`, timer active, service inactive 상태로 복구 여부를 확인할 예정입니다. 일반 `development-runner.json`의 기존 `paused=true`는 바꾸지 않습니다.

## 증거와 재개

- audit: 없음. API 응답 또는 dataset을 사용하지 않았습니다.
- 남은 작업·차단 조건: 최종 data source/allowlist·data acceptance 기준은 사용자 승인, provider 사용은 허용 계약과 필수 credential, 유료 plan은 실제 지출 승인 전까지 각각 보류합니다. `FINAL_VALIDATION`/OOS는 승인된 preregistration freeze 뒤 적격 PIT 및 미노출 미래자료가 생길 때까지 `PENDING/BLOCKED`입니다.
- 다음 시작: Massive 이력 조사와 겹치지 않도록 Alpha Vantage 등 이미 거론된 US source의 공식 조건·PIT/수정시점 근거를 무료 문서 범위에서 비교한 뒤 기존 cache 품질 공백과 함께 권고를 갱신합니다. 데이터 수집·final acceptance로 승격하지 않습니다.
