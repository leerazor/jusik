# Held-band cache 표본 수와 identity 재현

- 상태: 완료 (집계 메커니즘 재현; 원본 결과의 실행 code SHA 미결속)
- 기록 시각: 2026-09-27T06:25:15Z
- 작업 slug: `portfolio-held-band-sample-size-identity-reconcile`
- 기준/통합: `d9ba7a18a5de056253a350968f02f73e04240e9b` / `b573b1963abe16959e36290dac177bebfd38343d`
- 범위: 기존 US approximate cache에서 `sample_size=100`과 diagnostics 101 identities 차이를 오프라인으로 재구성했습니다. 원본 result/cache/receipt, mandate, v2 초안, collector/test와 운영 상태는 수정하지 않았습니다.

## 변경과 결정

- `20260922-us-vintage-collection-100`의 result SHA `a42fd8b4f53f1f05f39637dcff34806fa0fad17de6ad467acc40e0ae2a11ed7f`, completion marker SHA `6502980e37fc5cd6a281b4be5c00c4473ba3ac78a08b26ee0483a0411c9fe0f6`, cache manifest SHA `361e8de4fbdc8e66cc683a09109ac980ba5045991a65d93c5315b7dcd142c759`를 고정했습니다. 결과 hash는 marker와 일치합니다.
- raw Alpha listing checkpoint는 2025-08-13 및 2026-01-02 두 개입니다. 결정적 seed ordering을 replay해 각 checkpoint 100개, 두 번째 시점 overlap 99개, 신규 누적 identity 1개를 재현했습니다. 누적 고유 집합은 101개이며 diagnostics 101개와 정렬 identity-set SHA-256 `34aea723b851e437ba96df4e9151a0d04560c091c64bb1e7661ad689e8726288`가 일치합니다. 25개는 request-excluded, retained universe는 76개입니다.
- historical collector selection block은 capture candidate `61741cffa61e927b8838ed0084b7358f28f8e71b`, marker 완료 시점에 가까운 source candidate `5b732e1`, 현재 코드에서 동일 AST SHA `85097954fc6717e22f261cab55c3000ed34a8e46135448b24fe6c5d643eda369`였습니다. listing parser와 selection constants도 historical/current에서 일치합니다. 이 동작은 checkpoint별 sample cap 100 및 cumulative source-symbol 상한 400과 일치합니다.
- 따라서 `sample_size=100`과 diagnostics 101은 checkpoint별 표본 수와 여러 checkpoint의 누적 고유 identity 수 차이로 재현됩니다. 원 marker/result에는 source-code SHA가 없고, 원 cache manifest 137 entries에는 `request_descriptor`가 없어 정확한 runtime checkout을 증명하지 못합니다. 이는 실행 code provenance의 한계로 남깁니다.
- Mandate SHA `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`은 그대로입니다. Provisional assumption: 기존 pipeline semantics인 checkpoint별 최대 100개, cumulative source 최대 400개를 cache 재현 설명에만 적용합니다. 최종 연구의 sample 수치, data acceptance, preregistration 조건으로 동결하지 않습니다. mandate 변경이나 최종 합격 기준 선택은 사용자 승인 대상입니다.
- private replay script: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-sample-size-identity-reconcile/replay.py`, SHA-256 `2bf693745beaee866e145e5ff64d5cce2e11d888aad4f61859deef4004914772`.

## 문서·계약 영향

- 사용자 문서: held-band 결정 준비 문서에 재현 결과, provisional 해석과 runtime provenance 한계를 추가했습니다.
- 기존 cache profile 기록: 새 replay 결과 링크를 추가해 101-row cause가 아직 unresolved라는 과거 표현을 교정했습니다. 등록된 범위의 교차참조 정정입니다.
- 운영 문서: task 등록부와 기존 project handoff를 결과·다음 시작점에 맞춰 갱신했습니다.
- API·설정·데이터 계약: 변경 없음. `sample_size` 의미는 기존 코드·mandate를 읽어 재현했으며 formal criteria는 동결하지 않았습니다.

## 검증

- Offline replay 2회 — 모두 101 누적 identities, diagnostics와 sorted-set identity hash 일치, candidate selection/parser/constants 비교 일치.
- 재현 output SHA-256 — `06d392b6f8186a7240776fdd2c70a73107deafc3b0b832cd0e58a99840846887` 두 실행 동일.
- `ruff check` 및 `ruff format --check` — private audit script 통과.
- mandate SHA 및 v2 invariant — mandate 동일, unresolved 20개 모두 `null`, `registered=false`, `approved=false`, `execution_allowed=false`.
- 문서 상대 link와 code line anchor — 누락·범위 오류 없음. `git diff --check` — 통과.
- pytest/Ruff/typecheck — 제품 코드·테스트 변경이 없어 실행하지 않았습니다.
- 성과·simulation·OOS·자료 적격성·후보 승인 — 실행하지 않았습니다.

## 안전·운영 상태

- 기존 immutable result/cache와 two Alpha payload만 읽었습니다. manifest/result/raw hashes를 보존했습니다. endpoint, raw symbols, request values, credentials는 audit profile에 쓰지 않았습니다.
- Network/API/broker, account/key, 구매·비용, DB/cache write, PAPER/live, 주문, remote push는 없었습니다.
- clean task worktree는 제거하고 작업 branch는 보존합니다. 사용자 루트 `HANDOFF.md`는 수정하거나 stage하지 않았습니다.
- `FINAL_VALIDATION`/OOS만 승인된 preregistration freeze, eligible unexposed future data, PIT/data-contract checks 전까지 별도 `PENDING/BLOCKED`입니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-sample-size-identity-reconcile/profile.json`; SHA-256 `06d392b6f8186a7240776fdd2c70a73107deafc3b0b832cd0e58a99840846887`.
- 다음 runnable: 무료 공식 문서만 사용해 KRX 일별 주식·date-specific universe 후보의 access, coverage, terms를 검토하고 US 후보와 대안 영향을 비교합니다. 실제 credential·자료 요청·최종 market/source selection은 범위 밖입니다.
- exact runtime code identity는 입력에 없으므로 미확정으로 남기고, source candidate 기반 재현을 실험 결과나 strict PIT 증거로 사용하지 않습니다.
