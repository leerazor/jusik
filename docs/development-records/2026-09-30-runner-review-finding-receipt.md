# 독립 코드 검토 FAIL 지적 보존

- 상태: 기술 작업 완료. 기존 FAIL 후보는 `WAITING_EXTERNAL`로 유지합니다.
- 기록 시각: 2026-09-30T01:43:30Z
- 작업 slug: `runner-review-finding-receipt`
- 기준/통합: `129fe33f0ab022c5874440e8cc6370a6ab89d4fb` / `04e18a12c0d0a47826f135af1dc35b9ebb96d0e2` (local `main`)
- 범위: 새 reviewer FAIL receipt의 이유를 구조화해 private review 이력에 저장합니다. 자동 retry·재검토·승격과 과거 receipt 복구는 포함하지 않았습니다.

## 변경과 결정

- `ReviewFinding`은 정확한 소유 파일 경로, 양의 줄 번호, 문제 요약, 필요한 수정만 받습니다. finding은 최대 8개이며 두 문구는 각각 240자 이내입니다. 예상하지 못한 필드, 소유 경로 밖 값, 잘못된 identity/hash는 거부합니다.
- PASS에는 빈 `findings` 배열만 허용합니다. FAIL에는 실행 가능한 지적을 담도록 요청하고, 안전하고 구체적인 지적이 없으면 빈 배열도 허용합니다.
- 검증된 전체 receipt는 기존 `review_attempts.receipt_json`에 task·implementation attempt·review attempt·baseline/main HEAD·소유 파일 hash에 결속해 저장합니다. 지적 문자열은 신뢰하지 않는 자료이며 비밀값·개인정보·원시 transcript·임의 지시를 담지 않도록 안내합니다.
- FAIL은 계속 `review_rejected` / `WAITING_EXTERNAL`입니다. 일반 retry, event release, transport retry로 해제하지 않으며 자동 repair나 engineering/investment 승격도 하지 않습니다.
- 과거 `a17f257d0ae648d98e2320b638cdd670` receipt에는 verdict와 identity만 있어 이유를 복원하지 않았습니다. 후속 수리에는 현재 HEAD·소스 hash 기준의 새 task-local scope 검토와 새 독립 완료 검토가 필요합니다.
- 변경 파일: `backend/jusik/development_runner_review.py`, `backend/jusik/development_runner_store.py`, 네 개의 관련 runner 테스트, `docs/development-runner.md`.
- 독립 검토 첫 회에서 discovery fake reviewer의 `findings=[]` 누락을 찾았습니다. 범위 확장을 별도 검토받은 뒤 fixture만 보정했고, 전체 diff 최종 review는 PASS였습니다.

## 문서·계약 영향

- 사용자/운영 문서: `docs/development-runner.md`에 receipt 계약과 FAIL 대기 경계를 적었습니다.
- API·설정·데이터 계약: 공개 API나 투자자료 계약은 바뀌지 않았습니다. runner의 private review receipt schema만 확장했습니다.
- 아키텍처 문서: 모듈 경계나 시스템 구조 변화가 없어 갱신하지 않았습니다.

## 검증

- 통합 main에서 `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_development_runner_review.py backend/tests/test_development_runner_review_transport.py backend/tests/test_development_runner_roadmap_code_review.py backend/tests/test_development_runner_discovery.py -q` — **182 passed**.
- 관련 7개 Python 파일 `ruff check` 및 `ruff format --check` — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --config-file backend/pyproject.toml --strict backend/jusik/development_runner_review.py backend/jusik/development_runner_store.py backend/jusik/development_runner.py` — 3개 source 오류 없음.
- `git diff HEAD^1 HEAD --check` — 통과. 별도 reviewer는 최종 branch diff와 discovery 회귀 보정에 PASS했습니다.

## 안전·운영 상태

- 구현은 `/home/kwl/projects/jusik-runner-review-finding-receipt`의 Python 3.13.15 전용 환경에서 했고, 통합 뒤 main 환경에서도 focused 182개를 재실행했습니다.
- timer와 service는 개발 중 중지했고 runner DB는 paused입니다. 현재 선행 등록된 `project-memory-index` 문서 작업도 runner 정지를 유지하도록 지정되어 있어 이 기록 작업에서는 재개하지 않습니다. 그 작업의 최종 검토·통합 뒤 원래 timer를 재개해야 합니다.
- 외부 provider/API·credential·구매·운영 DB·PAPER/live·주문·remote push는 사용하지 않았습니다. 사용자 소유 루트 `HANDOFF.md`는 보존했습니다.

## 증거와 재개

- 기존 `roadmap-r2-02-manifest-integrity-guard-v1`의 FAIL은 구체적인 지적이 저장되지 않아 재개할 수 없습니다. 새 기능은 앞으로 생성되는 reviewer receipt에만 적용됩니다.
- R1-02/R1-05의 provider receipt에는 과거 `observed_at`과 범위·세션 정보가 필요하지만 들어올 시점은 확인되지 않았습니다. 이 코딩 작업은 외부 근거를 만들거나 투자 평가를 완료하지 않습니다.
- 다음 시작: [작업 등록부](../worktree-tasks.md)의 `project-memory-index` 진행 상태와 소유 worktree를 확인하고, 그 task의 독립 검토·통합이 끝났을 때 runner status와 timer를 확인한 뒤 재개합니다.
