# 빠른 수익성 결과를 위한 harness 우선순위

- 상태: 완료 (기술·정책 통합; 운영 재개는 별도 runtime 관측 기록)
- 기록 시각: `2026-09-29T02:50:49Z`
- 작업 slug: `fast-results-harness-priority`
- 기준: 등록 전 `bfdc8854ba9e20319a580511fb9fc820f9124410`; 작업 등록 `d7c59dd`.
- 구현/통합: `4d620ce`, `f82d844`, 독립 검토 보정 `eefee1ef47b20b553d060cc93e79c1e5ef923b1e`; local `main` fast-forward 통합.
- 사용자 목표: 현재 요금제를 계속 유지할 수 없고 시간이 부족하므로 개발 시간 단축, 빠른 결과, 수익률 극대화를 agent 전략의 최우선 운영 목표로 명시합니다.
- 범위: 프로젝트 공통·역할 지침과 자동 runner가 실제 전송하는 prompt의 우선순위입니다. 투자 수치 기준이나 미래 성과를 새로 정하는 작업이 아닙니다.

## 변경과 결정

- 기존 `COMMON_PROMPT`는 등록 시 붙는 지침으로 기존 대기열 및 독립 계획·검토·발굴 호출 전체를 포괄하지 않았습니다. 모든 실제 dispatch가 저장·전송하는 prompt에 공통 우선순위를 넣는 좁은 변경을 선택했습니다.
- 작업의 경제적 기여, 가장 이른 유용한 산출물, 제한된 작업 범위와 종료 조건을 기존 응답 형식 안에서 설명하도록 합니다. 구체적인 종료일·지출 한도·수익률 예측은 임의로 만들지 않습니다.
- 일반 작업·계획·완료 검토·roadmap 범위 검토·공학 발굴/범위 검토의 다섯 dispatch 지점에서 공통 지침을 붙입니다. 실제로 발송하는 입력과 저장된 `prompt.txt`가 같으며, `COMMON_PROMPT`가 없는 기존 큐 작업도 적용 대상입니다.
- 새 계획·발굴 제안은 다음 수익성 결과나 구체적 차단 해소와의 연결을 설명하고, 연결되지 않는 일반 공학 작업은 범위 검토에서 거절하도록 지시합니다. 완료 검토는 이미 동결된 인수 조건을 유지합니다. 결정적인 큐 정렬 알고리즘을 새로 구현한 것은 아닙니다.
- 독립 검토에서 반복 검사 금지가 필수 검사까지 생략할 수 있다는 지적을 받아 선택적 중복 호출만 줄이도록 보정했습니다. 작업별 focused 검사, 통합 검사, 독립 검토와 변경·실패·필수 gate에 따른 재검사는 보존합니다.

## 문서·계약 영향

- 정책 정본은 `docs/autonomous-trading-lab.md` §17입니다. 공통·역할 지침과 runner 운영 문서에서 실행 경로와 적용 범위를 설명합니다.
- 새 DB schema, 연구 mandate 수치, 비용 또는 권한 계약 변경은 이 작업 범위에 없습니다.

## 검증

- 조사·계획의 중앙 model-routing resolve/check와 사전·사후 라우팅 점검 PASS.
- 구현자 검사: fast-results·planning-scope·review pytest 39 passed, Ruff check/format, 변경 두 Python 파일 strict mypy(`--follow-imports=silent`), diff check PASS.
- 일반 strict mypy는 변경하지 않은 `backend/tests/test_development_runner_roadmap.py`에서 기존 오류 24건을 보고했습니다. 변경 파일 자체의 strict 검사는 통과했으며 이 작업에서 기존 테스트 파일을 보정하지 않았습니다.
- 최종 main: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_development_runner_fast_results.py` — 4 passed. 계획·roadmap scope·발굴·발굴 scope·완료 review·기존 큐의 실제 fake-child stdin과 저장 prompt의 byte equality를 검사합니다.
- main Ruff check/format과 `mypy --strict --follow-imports=silent --config-file backend/pyproject.toml`(변경 Python 두 파일), `git diff --check d7c59dd..eefee1e` PASS. Python 3.13.15; 6개 role TOML parse 및 priority 지침 확인 PASS.
- 최종 독립 review PASS. explore/Luna-medium, plan/Sol-high, code/Sol-high(3 turns), review/Sol-high의 중앙 선택·사전 및 실제 model/effort 사후 검사 PASS.
- 범위 밖 전체 suite와 투자 실험은 실행하지 않았습니다. 이 작업은 시간 절감량이나 수익 개선을 측정하지 않았습니다.

## 안전·운영 상태

- 수동 변경 전 roadmap runner의 unpaused 상태와 timer active를 확인하고 pause·service inactive로 전환했습니다. 기록 commit과 tracked clean 확인 후 이전 실행 상태로 재개하며 실제 새 호출 적용은 아래 runtime 기록으로 확인합니다.
- 기존 `main`은 기준 저장소 `/home/kwl/projects/jusik`에 있습니다. 완료된 이전 통합용 checkout을 새 전용 branch로 재사용했습니다. 사용자 소유 루트 `HANDOFF.md`는 보존합니다.
- 원격 push·실험·시장자료·주문·PAPER/live 변경은 수행하지 않았습니다.

## 증거와 재개

- 영구 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-fast-results-harness/`; `integration-pytest.log`, `routing-audit.json`, `runtime.json`. runtime은 재개 후 새 실제 attempt와 priority prefix 일치 관측을 기록합니다.
- 남은 제품·정책 수정: 없음. 기존 연구의 자료·OOS·실주문 승인 조건은 별도이며 새 수익성 증거는 없습니다.
- 다음: `AGENTS.md`의 최우선 목표와 이번 handoff를 읽고, 다음 결과의 경제적 기여·소요 범위·차단 해소를 먼저 확인합니다. trust-boundary 결정은 직접 필요한 결과의 선행조건일 때만 우선합니다.
