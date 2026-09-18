# KOFR 원천 증거 수집

- 상태: 차단
- 기록 시각: 2026-09-17T12:13:04Z
- 작업 slug: `kofr-risk-free-source-evidence`
- 기준/통합: `efbf82cf0e8d9d7de31a4d8daa7df0231ce73400` / 없음
- 범위: 공식 KOFR 일별 원문의 bounded collector·parser·verifier와 fake-transport 테스트를 전용 워크트리에 구현했습니다. readiness, metrics, policy, strategy, runner, API는 변경하지 않았습니다.

## 변경과 결정

- 공식 KSD 응답은 root `<vector result="N">`와 N개의 sibling `<data><result>...</result></data>` 구조입니다. 첫 공식 요청 당시 후보가 다른 구조를 가정해 `invalid_record_count`로 차단됐습니다.
- 공식 `rate/rate.jsp`의 tracked WebSquare XML(`/pub/rate/rate.xml`)을 읽기 전용 대조한 결과, 화면이 호출하는 task는 `rate.process.RatePTask`입니다. 기존 후보의 `ksd.rfr.user.rate.process.RatePTask`는 endpoint 계약과 불일치했습니다.
- candidate `720f6dc`에서 task 상수를 `rate.process.RatePTask`로 교정했고 fake transport pytest 21개와 Ruff/format 검사를 통과했습니다. 실제 공식 재요청과 raw evidence 생성은 아직 수행하지 않았습니다.
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
- 공식 요청: 1회. 초기 parser 계약 실패. task 계약 교정 후에도 추가 요청 0회.

## 안전·운영 상태

- 실제 주문, PAPER/live, 연구 실행, 운영 DB·서비스·설정, 원격 push를 수행하지 않았습니다. 자동 runner는 재개하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-kofr-risk-free-source-evidence`; `attempt.json`과 `request.xml`만 존재합니다.
- 보존: `/home/kwl/projects/jusik-kofr-risk-free-source-evidence`, branch `feat/kofr-risk-free-source-evidence`, candidate `3fcb553`.
- 남은 작업·차단 조건: task 계약은 교정됐지만 새 audit attempt와 두 번째 공식 요청을 별도 승인·계획하고, 성공 raw/evidence를 후보와 함께 전체 도구 검사해야 통합할 수 있습니다.
- 다음 시작: KOFR 재수집과 독립적으로, 명시적 initial-capital event와 per-NAV UTC timestamp를 생성하는 forward-only simulation artifact를 조사·설계합니다.
