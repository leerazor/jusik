# KOFR 원천 증거 수집

- 상태: 차단
- 기록 시각: 2026-09-17T12:13:04Z
- 작업 slug: `kofr-risk-free-source-evidence`
- 기준/통합: `efbf82cf0e8d9d7de31a4d8daa7df0231ce73400` / 없음
- 범위: 공식 KOFR 일별 원문의 bounded collector·parser·verifier와 fake-transport 테스트를 전용 워크트리에 구현했습니다. readiness, metrics, policy, strategy, runner, API는 변경하지 않았습니다.

## 변경과 결정

- 공식 KSD 응답은 root `<vector result="N">`와 N개의 sibling `<data><result>...</result></data>` 구조입니다. 첫 공식 요청 당시 후보가 다른 구조를 가정해 `invalid_record_count`로 차단됐습니다.
- 공식 `rate/rate.jsp`와 `/js/common.js`를 읽기 전용 대조했습니다. 화면은 `rate.process.RatePTask`를 넘기지만 `_doTask`가 `ksd.rfr.user.` prefix를 자동으로 붙이므로 candidate의 전체 task `ksd.rfr.user.rate.process.RatePTask`는 유효합니다.
- 시험적으로 만든 task 단축 commit `720f6dc`는 공식 요청 결과가 XML 선언만 반환되어 실패했고, candidate `4b6490f`에서 원래 전체 task를 복구했습니다. fake transport pytest 21개는 복구 후 통과했습니다.
- 후보 `3fcb553`은 실제 관측 구조, bounded Decimal 무손실 정규화, 정확한 XML tag·attribute·text 계약, request/raw SHA, descriptor-relative `O_NOFOLLOW`와 상위 symlink 거부를 구현했습니다.
- 실패 후 공식 요청을 반복하지 않았습니다. 성공 evidence JSON이 없으므로 후보를 local `main`에 병합하지 않습니다.
- KOFR source evidence는 향후에도 interval 적용 근거가 아닙니다. 초기자본/NAV UTC timestamp, 공표 instant·timezone, 기대 영업일 완전성, scalar 축약과 복리 정책을 별도로 증명해야 합니다.

## 문서·계약 영향

- 사용자 문서: 후보 브랜치가 `docs/market-performance-metrics.md`에 source와 application evidence 분리를 기술하지만 미병합입니다.
- 운영 문서: 해당 없음. 운영 서비스·DB·설정을 변경하지 않았습니다.
- API·설정·데이터 계약: main 변경 없음. 후보 schema도 end-to-end 검증 전에는 정본이 아닙니다.

## 검증

- 표준 라이브러리 fake-transport harness — 정상/위협/Decimal/path/XML 회귀 통과.
- `python -m py_compile`, `python -m compileall`, `git diff --check` — 통과.
- Terra 독립 재검토 — `3fcb553` PASS, P1/P2 없음.
- 실행하지 않은 검사: 전용 worktree에 pytest/Ruff/mypy 환경이 없어 실행하지 못했습니다.
- 공식 요청: 2회. 첫 요청은 parser 계약 실패, 두 번째 요청은 XML 선언만 반환되어 `malformed_xml`로 fail-closed했습니다. 두 번째 audit의 raw SHA와 failure 기록을 보존했습니다.

## 안전·운영 상태

- 실제 주문, PAPER/live, 연구 실행, 운영 DB·서비스·설정, 원격 push를 수행하지 않았습니다. 자동 runner는 재개하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-kofr-risk-free-source-evidence`; `attempt.json`과 `request.xml`만 존재합니다.
- 보존: `/home/kwl/projects/jusik-kofr-risk-free-source-evidence`, branch `feat/kofr-risk-free-source-evidence`, candidate `3fcb553`.
- 남은 작업·차단 조건: task 계약은 유효하지만 공식 응답이 비어 있어 성공 evidence가 없습니다. 추가 요청은 새 승인·계획 없이는 수행하지 않으며, 응답 원인·필수 요청 상태를 확인한 뒤 성공 raw/evidence가 있을 때만 후보를 전체 도구 검사·통합합니다.
- 다음 시작: KOFR 재수집과 독립적으로, 명시적 initial-capital event와 per-NAV UTC timestamp를 생성하는 forward-only simulation artifact를 조사·설계합니다.
