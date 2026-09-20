# Public evidence symbol boundary

- 상태: 완료된 기술 slice; `coverage=incomplete`, 경제 acceptance와 R1 checkbox는 유지
- 기록 시각: 2026-09-20T00:02:47Z
- 작업 slug: `r1-public-evidence-symbol-boundary-20260920`
- 기준/통합: `695634e` / 통합 전
- 범위: 요청 universe 밖의 Nasdaq halt, Alpha action, SEC filing을 catalog에 포함하지
  않도록 fail-closed 검증과 source별 회귀 테스트를 추가했습니다. collector, network,
  ledger, PAPER/live, 실제 주문, 원격 push와 기존 fixed artifact는 변경하지 않았습니다.

## 변경과 결정

- `build_public_evidence_catalog()`는 각 source item의 symbol 또는 SEC CIK→ticker
  mapping 결과가 `requested_symbols`에 없으면 `ValueError("evidence_symbol_not_requested")`
  를 발생시킵니다.
- 검증은 event date 범위 필터보다 먼저 수행하여 요청 기간 밖 자료라도 다른 universe의
  evidence가 조용히 버려지거나 섞이지 않게 했습니다.
- 기존 정상 catalog, SEC `unresolved_symbols`, source-specific duplicate 제거,
  `coverage="incomplete"` 및 catalog digest 계약은 보존했습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 내부 fail-closed catalog 입력 계약과 테스트만 보강했습니다.
- 운영 문서: 해당 없음. runner/service/timer 상태를 변경하지 않았습니다.
- API·설정·데이터 계약: PublicEvidenceCatalog builder가 요청 외 symbol을 거부하는
  검증 계약을 추가했습니다. schema version과 digest 형식은 유지했습니다.

## 검증

- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest backend/tests/test_research_public_evidence_catalog.py -q` — 7 passed
- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest backend/tests/test_research_public_evidence_catalog.py backend/tests/test_research_public_evidence.py backend/tests/test_research_alpha_actions.py backend/tests/test_research_sec_evidence.py -q` — 18 passed
- `.../bin/python -m ruff check backend/jusik/research_public_evidence_catalog.py backend/tests/test_research_public_evidence_catalog.py` — 통과
- `.../bin/python -m ruff format --check backend/jusik/research_public_evidence_catalog.py backend/tests/test_research_public_evidence_catalog.py` — 2 files already formatted
- `/home/kwl/projects/jusik/backend/.venv/bin/python -m mypy --config-file backend/pyproject.toml backend/jusik/research_public_evidence_catalog.py` — 변경 모듈 자체 진단 0건. imported source module의 기존 진단 5건(`research_public_evidence.py`, `research_alpha_actions.py`, `research_sec_evidence.py`)은 이 작업 범위에 포함하지 않았습니다.
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·원격 push·서비스 재개·운영 데이터 변경은 없습니다.
- 기존 source raw receipt와 fixed artifact는 재생성하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 기존 catalog hash 불변
- 남은 작업·차단 조건: 실제 receipt coverage, PIT publication, 권리·가격 자료가
  부족하므로 경제 acceptance와 R1 승격은 보류합니다.
- 다음 시작: Astra가 이 브랜치를 독립 검토 후 local `main`에 통합하고 통합 검증을 실행합니다.
