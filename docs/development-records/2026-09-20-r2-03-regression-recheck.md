# R2-03 회귀 재검증

- 상태: 기술 회귀 검증 완료·KOFR/포트폴리오 경제 적용 미완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r2-03-regression-recheck-20260920`
- 기준/통합: `b5a101f` / 문서 변경 후 통합 예정
- 범위: R2-03 관련 FX provenance, 포트폴리오 회계 evidence, KOFR 적용, receipt journal의 회귀와 strict typing을 재검증했습니다. 기존 fail-closed 정책과 경제 승격 보류 상태는 보존했습니다.

## 변경과 결정

- 코드 변경은 하지 않았습니다. 기존 exact-date KOFR 정책, missing risk-free evidence 차단, FX/회계 evidence 경계를 그대로 유지합니다.
- 테스트가 통과해도 자료의 완전성이나 경제적 유효성이 증명되는 것은 아니므로 R2-02/R2-03 경제 acceptance와 PAPER/live 승격은 진행하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자에게 보이는 동작·설정 계약은 변경하지 않았습니다.
- 운영 문서: `docs/worktree-tasks.md`에 검증 상태를 등록합니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_research_fx_provenance.py backend/tests/test_research_portfolio_accounting_evidence.py backend/tests/test_kofr_application_evidence.py backend/tests/test_research_receipt_journal.py -q` — `60 passed`.
- `backend/.venv/bin/python -m mypy --strict backend/jusik/research_fx_provenance.py backend/jusik/research_portfolio_accounting_evidence.py backend/jusik/kofr_application_evidence.py` — 통과.
- `git diff --check` — 통과.
- 실행하지 않은 검사: 전체 저장소 검사는 이전 번들에서 통과했으며 이번 변경은 문서뿐이므로 재실행하지 않았습니다.

## 안전·운영 상태

- 실주문·PAPER/live 승격·원격 push·Windows 종료를 수행하지 않았습니다.
- 개발 runner service는 inactive, timer는 disabled 상태를 유지해야 합니다.

## 증거와 재개

- audit: 기존 KOFR/FX/회계 evidence audit 경로; 새 원시 자료 없음.
- 남은 작업·차단 조건: KOFR exact-date coverage, 비용 계약, PIT completeness가 충족될 때까지 경제 성과 평가와 R2 승격은 차단됩니다.
- 다음 시작: `docs/worktree-tasks.md`, `docs/research-mandate.json`, `docs/roadmap.md`를 읽고 다음 우선순위의 차단 조건을 하나씩 해소합니다.
