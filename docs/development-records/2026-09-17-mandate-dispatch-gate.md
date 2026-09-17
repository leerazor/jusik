# Mandate dispatch gate

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `mandate-dispatch-gate`
- 기준/통합: `7da06b9` / 없음
- 범위: 기존 historical mandate 필드를 보존하면서 versioned governance를 추가하고, investment-roadmap runner의 dispatch·resume를 fail-closed 검증합니다. 일반 research scope, DB schema, PAPER10% 계약은 변경하지 않습니다.

## 변경과 결정

- `backend/jusik/research_mandate_governance.py`가 중복 key, strict type, 문서 regular-file, JSON·Markdown·manifest hash, 정책 version 및 roadmap marker를 검증합니다.
- `dispatch_enabled=false`인 tracked governance를 유지해 실제 자동 실행은 비활성 상태입니다. roadmap planner fingerprint에는 검증된 mandate digest를 포함하고 enqueue 직전에 재검증합니다.
- 전체 roadmap SHA는 JSON governance에 복사하지 않습니다.

## 문서·계약 영향

- 사용자 문서: `docs/research-mandate.md`, `docs/research.md` — governance와 scope 경계를 설명합니다.
- 운영 문서: `docs/development-runner.md`, `docs/roadmap-automation.md` — fail-closed gate를 설명합니다.
- API·설정·데이터 계약: `docs/research-mandate.json`에 additive governance object를 추가했으며 기존 historical/PAPER 필드를 보존합니다.

## 검증

- `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_research_mandate_governance.py backend/tests/test_development_runner.py backend/tests/test_development_runner_planning.py backend/tests/test_development_runner_roadmap.py -q` — 104 passed.
- `backend/.venv/bin/ruff check ...` 및 `ruff format --check ...` — 통과.
- `PYTHONPATH=. backend/.venv/bin/python -m mypy --strict ...` — 통과.
- JSON/Markdown/checksum/policy marker 보존 검사와 `git diff --check` — 통과.
- 실행하지 않은 검사: 실제 runner resume/dispatch, 연구·수집·PAPER/live·주문, 운영 DB·서비스·remote 변경.

## 안전·운영 상태

- 실제 주문, PAPER/live 상태, 운영 DB, 서비스, 외부 수집, 배포와 remote push를 변경하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: tracked checksum manifest를 최종 JSON·Markdown에 맞춰 갱신합니다.
- 남은 작업·차단 조건: 독립 review 후 Astra가 local main에 통합해야 합니다.
- 다음 시작: main 통합 전 validator·runner focused 검증을 재실행합니다.
