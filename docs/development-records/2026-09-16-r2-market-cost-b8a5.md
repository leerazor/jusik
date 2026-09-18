# R2-02 시장별 비용 진단 — 중단 이력과 복구

현재 상태: 기술 복구·독립 검토·local main 통합 검증 완료. 실제 자료 근거 부족으로 전체 로드맵 항목은 미완료입니다. 아래 최초 상태는 과거 시도 이력입니다.

- 상태: 차단·미통합. 기술 slice 미완료, 경제 평가 not-evaluated.
- 기록 시각: 2026-09-16T07:43:27.955856+00:00
- 작업 slug: `r2-market-cost-b8a5`
- task/attempt: `roadmap-r2-02-v1` / `b8a573f2cb564b6cb46ea646452071e5`
- 시작 main: `baa192591a4ccf9a8cc9a21623ca075bacc8acc3`; 등록부 준비 commit: `b88850c`; 구현 commit: `ed03e2c647bfec876eee4d9e5a1b23c4562e758e`; 구현 통합 없음.

## 변경과 결정

Luna는 전용 워크트리에 독립 Decimal 진단 모듈, 테스트, 한국어 계약과 개발 기록을 작성했습니다. 이 구현은 승인되지 않았고 main에 병합하지 않았습니다. main에는 기존 작업 등록부와 이 중단 기록만 남깁니다. 전략·shared model·고정 세율은 변경하지 않았습니다. R2-01 및 다른 격리 작업 코드는 재사용하거나 재개하지 않았습니다.

초기 검사 batch에서 동일한 `ruff._find_ruff.RuffNotFound` 오류가 두 번 발생했습니다. 작업자는 이후 검사를 계속했으나 사용자 중단 조건에 위배됩니다. 감독이 반환 결과와 실제 실행 출력을 확인한 뒤 추가 구현·검사·병합을 중단했습니다. 사후 통과는 이 중단 조건을 해소하지 않습니다.

## 검토와 검증

- 입력: 첨부 evidence5개, main SHA, 최신 mandate, 동결 artifact4개 및 cache raw84개 SHA/size 검증 통과.
- 감독 독립 산술: 저장 US pilot252세션/106거래의 체결가·금액·fee·매도세가 구현 가정과 일치했습니다. 원본은 읽기 전용이며 simulation/replay를 실행하지 않았습니다.
- 작업자 후속 검사: pytest19개, Ruff check/format, configured strict mypy 및 저장 pilot 대사는 통과 기록이 있습니다. 최초 pytest/mypy 실패와 동일 Ruff 환경 실패2회도 보존했습니다. 중단 조건 위반 후 결과이므로 전체 tests_passed=false입니다.
- Terra 독립 review: FAIL. 동일 실패2회 중단 위반, 저장값 불일치의 success 처리, 매수 독립 기대값·이중 비용 검증 누락, 시간대 경계·chronology 검증 부족, 16개 고정 시나리오 외 추가 assumptions 입력4개를 지적했습니다.
- local main 통합 검사: 미실행. 구현 병합이 차단되어 실행하지 않았습니다. review_passed=false, integrated_commit=null입니다.
- 입력 자료의 법정 세목·관할·유효기간·출처와 실제 체결 timestamp·부분체결·취소/거절 이력·거래소 휴장일 근거가 부족합니다. 공통0.0018은 구현 가정이며 법정 세율이 아닙니다. 전체 R2-02 checkbox는 미체크를 유지합니다.

## 문서·계약 영향

main의 사용자/API/설정 계약은 변경되지 않았습니다. 제안 계약은 미병합 워크트리 및 audit source-snapshot에 보존했습니다. 새로운 성과 비교가 없어 웹 수치 공개는 하지 않았습니다.

## 안전·운영 상태

network·simulation/replay·GPU 실행0회입니다. PAPER/live 활성화·실제 주문·운영 원장/DB·서비스/설정·remote 변경은 하지 않았습니다. 기존 root HANDOFF.md와 다른 워크트리는 보존했습니다. 계산 검사900초 또는 artifact20MiB 한도 초과는 관측되지 않았지만 fixture 상한 위반이 확인되었습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-02-b8a573f2`. `worker-initial-check-output.txt`와 `worker-failure-markers.json`은 동일 실패2회 증거, `review.md`는 독립 지적, `source-snapshot`과 `implementation.patch`는 미병합 구현 보관본입니다. `manifest.json`은 보관 증거 SHA 목록입니다.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-02-b8a573f2/HANDOFF.md`.
- 소유 워크트리 `/home/kwl/projects/jusik-r2-market-cost-b8a5`, 브랜치 `feat/r2-market-cost-b8a5`를 미병합 상태로 보존합니다. 정리 조건을 충족하지 않아 제거하지 않습니다.
- 재개에는 명시적 retry와 새 계산/fixture 한도가 필요합니다. 같은 소유 브랜치를 재사용하고, 환경 executable 준비를 검사 전에 확인한 뒤 독립 review 지적을 고쳐야 합니다. 동일 attempt에서 추가 수정·검사를 하지 않습니다. 전체 R2-02 완료에는 시장별 공식 비용·세목·유효기간 근거가 추가로 필요합니다.

## 승인된 복구 기록

- 복구 계획: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-cost-recovery/PLAN.md`; 과거 Ruff 중단 조건 위반과 실패 기록은 보존하고 이번 시도와 구분합니다.
- `market_cost_diagnostics.py`는 저장값 mismatch·구조 오류를 `invalid`와 `stored_match=false`로 우선 처리하고, timezone-aware 체결 시각을 US `America/New_York`·KR `Asia/Seoul` 현지 날짜와 대조합니다. 거래 session 감소, equity session 중복·비증가, equity에 없는 fill session, 완전 동일 관측 중복을 fail-closed로 처리합니다.
- 테스트는 실제 pilot 파일을 읽지 않고 monkeypatch한 SHA·개수의 작은 합성 JSON을 사용합니다. 16개 named scenario inventory 안에서 UTC 경계·US DST·KR 경계, 역순 session, equity/fill 경계와 malformed assumptions를 검증하고, KR/US 매수·매도 및 왕복 literal Decimal 기대값을 독립 대조합니다.
- 확인: `PYTHONPATH=. .venv-r2/bin/python3.13 -m pytest tests/test_market_cost_diagnostics.py -q` — 20 passed. Ruff·strict mypy·diff·환경 버전과 실제 pilot 1회 결과의 원문·exit·wall·CPU는 `/home/kwl/.local/share/jusik/portfolio-audit/20260916-cost-recovery/worker/recovery-checks.json` 및 `recovery-pilot-diagnostics.json`에 보관합니다.
- 복구에서도 statutory tax types, jurisdiction, effective period, official rates, exchange holiday calendar, actual fill timestamp/order identity는 unavailable이며 R2-02 전체와 경제 평가는 blocked/not-evaluated입니다.

## 감독 통합 검증

- 현재 기술 상태: 복구 완료. 기존 blocked 시도는 runner 이력에 보존하며 전체 R2-02는 미완료입니다.
- 독립 Terra review `6e7aab6`: P1/P2 없음. 병합 직전 main `d90757c`, 통합 `79e73c6`.
- main focused pytest20·Ruff check/format·configured strict mypy2파일·diff check 통과. 제품/테스트/계약 소스가 검토한 worktree와 같음을 확인하여 pilot 증거를 재사용했습니다.
- 개발 기록 충돌은 main의 실패 기록을 기준으로 복구 섹션을 덧붙여 해결했습니다. 과거 결과를 성공으로 바꾸지 않습니다.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20260916-cost-recovery/integration.json`, `integrated/`, `source/`. 소스·패치·SHA 보관 후 병합된 worktree와 branch를 정상 제거했습니다.
- 웹·전략·실제 요율·공개 성과·PAPER/live·운영DB·원격push 변경 없음. 자동 개발은 세 복구의 통합 종료 후 재개합니다.

## Output 보존 보완

- 최신 독립 검토의 P1에 따라 CLI가 진단 전에 `--pilot`·`--output`의 resolve 및 existing `samefile` 별칭을 검사하도록 보완했습니다. 동일 경로·symlink·hardlink는 exit 2로 거부하며 pilot bytes를 보존합니다. 별도 output 경로의 정상 기록은 유지합니다.
- 합성 fixture로 동일·symlink·hardlink·정상 별도 경로를 검증합니다. 실제 frozen pilot은 계산 변경이 없어 재실행하지 않습니다. 상세 명령·원문·시간·exit는 `/home/kwl/.local/share/jusik/portfolio-audit/20260916-cost-recovery/output-guard/`에 보관합니다.

## 원본 보존 후속 검증

- 추가 독립 검토에서 CLI 입력과 출력의 동일/별칭 경로로 원본을 덮어쓸 수 있는 P1을 확인했습니다. 실제 원본 덮어쓰기는 실행하지 않았습니다.
- 같은 Luna가 새 전용 worktree에서 `resolve`/`samefile` 사전 거절과 동일·symlink·hardlink 원본 보존 회귀를 구현했습니다. 구현 `6831e49`, Terra 재검토 PASS, 통합 `daf7ba5`.
- main focused pytest21·Ruff check/format·configured strict mypy·diff check PASS. 비용 산술은 그대로이며 실제pilot 재실행 없이 합성 CLI 입력으로 경로 보호를 검증했습니다.
- audit `20260916-cost-recovery/output-guard`의 checks·integration·source를 보존한 뒤 후속 worktree와 branch도 정상 제거했습니다.
- 최초 재사용 review agent의 전체 native post 감사는 과거 turn_context 누락으로 실패했습니다. 이를 `20260916-loss-recovery/role-audit.json`에 보존하고, 현재 native reviewer로 재검토하여 원본 보호 결함 발견·해소와 최종 수용을 확인했습니다.
