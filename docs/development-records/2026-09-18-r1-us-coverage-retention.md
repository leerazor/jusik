# 미국 membership checkpoint coverage retention

- 상태: 완료
- 기록 시각: 2026-09-17T19:18:00Z
- 작업 slug: `r1-us-coverage-retention`
- 기준/구현/통합: `27d8246cd074999e0e11e3d495453d31e78486b8` / `a47b1a85ff241afb96e31b049f64c387dbbb21e8` / `adb41e1e20c3e8aa92c9f4d939d7d794ab607106`
- 범위: 기존 미국 근사 collector와 collection diagnostics에 실패한 후속 membership
  checkpoint 구간의 bounded unknown evidence를 추가했습니다.

## 변경과 결정

- `MembershipGap`은 실패 checkpoint 날짜, 기존 market-session의 정확한 immutable `sessions`
  tuple과 경계/count, 당시 incumbent 심볼, `alpha_vantage` source와 `unknown` status를
  frozen 모델로 보존합니다. 모델은 tuple 정렬·유일성·경계·count를 대사합니다.
- gap은 후속 checkpoint 실패에만 생성하며 첫 checkpoint 실패의 기존 중단 동작은 유지합니다.
  연속 실패는 checkpoint 경계로 나누고 회복 시 회복 checkpoint의 causal effective session
  직전에서 닫으며, terminal failure는 요청 종료일까지 닫습니다.
- gap 심볼은 당시 current pool의 복사본만 사용합니다. 누적 admitted, 이후 newcomer, 이전
  pool에서 제거된 심볼을 합성하지 않습니다.
- gap symbol union과 `membership_unknown` reason-bearing diagnostics를 엄격히 대조합니다.
  가격 coverage 수치와 universe·bars·candidate·strategy 입력은 변경하지 않습니다.
- 빈 `membership_gaps`는 JSON에서 생략되며, 누락된 legacy field는 빈 tuple로 역직렬화됩니다.

## 문서·계약 영향

- `docs/market-research.md`에 gap 진단 계약과 legacy compatibility를 기록했습니다.
- 전략·snapshot/result/replay schema, runner/PAPER/live, 주문, 운영 DB와 service는 변경하지
  않았습니다. R1-05 checkbox는 유지합니다.

## 검증

- worker collector/approximate pytest — 169 passed.
- main collector/approximate/replay pytest — 182 passed.
- main Ruff check, configured mypy for changed production sources, `git diff --check` — 통과.
- Terra 독립 최종 review — PASS, P1/P2 없음.
- 전체 파일 Ruff format은 기존 범위 밖 formatting 차이 때문에 gate로 사용하지 않았습니다.
- 실제 provider/network 수집, 연구 실행, PAPER/live 주문은 수행하지 않았습니다.

## 남은 제한

- 실제 provider receipt와 실패 원인은 여전히 `unknown`이며, membership gap은 이를 합성하지
  않습니다. historical receipt·suspension·corporate-action 회계가 없는 기존 제한도 유지합니다.
- 다음 시작: R1-04 corporate-action 회계에서 현재 확보된 action 근거와 missing 정책 중 외부 수집 없이 구현 가능한 최소 선행 계약을 다시 대조합니다.
