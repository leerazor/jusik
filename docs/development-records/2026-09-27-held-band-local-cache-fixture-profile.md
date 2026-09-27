# Held-band 기존 로컬 cache fixture profile

- 상태: 완료 (offline 개발 fixture의 품질·provenance 진단; 자료 적격성 판정 아님)
- 기록 시각: 2026-09-27T06:01:03Z
- 작업 slug: `portfolio-held-band-local-cache-fixture-profile`
- 기준/통합: `0cc78137798c81ce56ab5c8e893929f9f9d05ecc` / `7881d7f4c6cbac2982ec380c2c178e7ddc003e5f`
- 범위: 기존 US approximate 결과/cache와 Alpha Vantage listing receipt를 읽기 전용으로 대조했습니다. 연구 mandate, agent 역할, 제품 코드·테스트, 원본 자료, v2 초안과 사용자 루트 `HANDOFF.md`는 수정하지 않았습니다.

## 변경과 결정

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)에 기존 cache의 coverage 분모, 종목별 bar 결손, orphan bar, 중복·수치 품질, action/FX 시각 및 manifest 무결성 결과를 기록했습니다.
- 전체 expected 27,472는 diagnostics의 101개 고유 심볼×272세션과 일치합니다. 후속 offline replay는 `sample_size=100`이 checkpoint별 선택 cap이고 두 checkpoint 간 cumulative unique symbol union이 101개인 원인을 재현했으며, 자세한 hash 비교와 runtime-code caveat는 [identity 재현 기록](2026-09-27-held-band-sample-size-identity-reconcile.md)에 있습니다. 원본 result가 실행한 exact code SHA는 여전히 기록되지 않았습니다. 제외 25개 심볼의 expected 6,800을 분리하면 포함 universe 20,672 중 20,306 bars가 있으며 실제 membership bar 결손은 366개(LIME 221, MDA 145)입니다. 별도의 98 PTN bars에는 membership row가 없어 임의 join하지 않습니다.
- 중복 membership/bar key, 잘못된 OHLC, 결측 수치, 음수 volume은 0입니다. 272 FX행은 중복 없이 날짜/시각이 parse 가능하지만 timestamp는 정확한 공개시점이 아닙니다. 121 corporate-action행 모두 `observed_at`이 없습니다.
- Alpha Vantage listing receipt는 2026-09-22 수집, 25개 요청 중 24개 일치·1개 미일치였고 receipt의 `observed_at`은 시각이 아닌 “provider publication timestamp unavailable” 문구입니다. 역사 날짜를 나중에 조회한 자료로, 동시대 관측 증거로 해석하지 않습니다.
- collector의 `available_at`은 membership의 checkpoint session close, Yahoo bar의 market session close, FRED vintage date 다음 날 자정 convention으로 생성됩니다. 기술적 causal guard 및 fixture 메타데이터로는 확인 가능하지만 provider publication/revision PIT를 입증하지 않습니다.
- private audit profile은 `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-local-cache-profile/profile.json`에 보존했습니다. SHA-256 `495e363ebd37fdc7bcbe7f82974df76219b8b995cfed77061adc0aa323723e8e`. 원본 cache 137개 raw payload의 manifest content hash, completed output hash binding은 일치했습니다.
- provisional assumption: 노출된 approximate 자료는 offline parser·coverage·결손 표시·회귀 fixture 개발에만 사용할 수 있습니다. 성과, strict PIT, source/data acceptance, OOS, 신규 후보 승인 또는 실거래 근거로 승격할 수 없습니다. 이를 v2 필드 또는 최종 기준에 고정하지 않습니다.

## 문서·계약 영향

- 사용자 문서: held-band 결정 준비 문서에 fixture 범위와 실제 제한을 추가했습니다.
- 운영 문서: 작업 등록부 및 기존 project handoff를 최신 완료·재개 상태로 갱신했습니다.
- API·설정·데이터 계약: 해당 없음. existing collector timestamp assignment를 읽기 전용으로 조사했습니다.

## 검증

- Offline profile generation / hash reconciliation — 완료. source raw 파일은 읽기만 했고 입력 manifest·output binding을 재검증했습니다.
- mandate SHA-256 — `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1` 동일.
- v2 JSON — `unresolved_before_registration` 20개 field 모두 `null`; `registered`, `approved`, `execution_allowed`는 모두 `false`.
- 결정 준비 문서·개발 기록·handoff의 상대 Markdown link 검사 — 누락 없음.
- `git diff --check` — 통과.
- pytest/Ruff/typecheck — 문서-only 변경이며 제품 코드·테스트는 바꾸지 않아 실행하지 않았습니다.
- 성과·전략 시뮬레이션·OOS·자료 적격성 — 실행하지 않았습니다.

## 안전·운영 상태

- 외부 시장자료 API, broker API, network collection, account/key, 구매/비용, DB/cache write, PAPER/live, 주문, remote push는 없었습니다. existing raw data는 그대로 두었습니다.
- task worktree는 clean 상태로 제거했고 작업 branch는 보존했습니다. 사용자 작성 루트 `HANDOFF.md`는 수정하거나 stage하지 않았습니다.
- 실제 새 provider 수집은 required credentials 및 사용권 검토 없이는 보류됩니다. `FINAL_VALIDATION`/OOS는 적격 미노출 미래자료 및 승인된 preregistration freeze 전까지 별도 `PENDING/BLOCKED`입니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-local-cache-profile/profile.json`; private artifact SHA 위 참조.
- 다음 runnable: 등록한 `portfolio-held-band-sample-size-identity-reconcile` task에서 immutable request/cache receipts와 이전 request descriptor를 대조합니다. 해소되지 않으면 unknown으로 유지하며 membership 자동 조인이나 성과 산출은 하지 않습니다.
- 차단 항목은 위 실제 provider 접근 및 최종 OOS뿐이며, 독립적인 오프라인 품질·pipeline 작업은 계속 가능합니다.
