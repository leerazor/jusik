# Canonical time-evidence sidecar

- 상태: 완료
- 기록 시각: 2026-09-20T01:00:00Z
- 작업 slug: `canonical-time-evidence-sidecar-20260920`
- 기준/통합: `206e1fa` / `fe4b1a5`
- 범위: frozen R0 run을 변경하지 않고, tracked XNYS calendar에서 파생한 시간 증거를 별도 sidecar로 생성·검증했습니다.

## 변경과 결정

- `research_canonical_time_evidence.py`는 canonical run/manifest의 SHA chain, candidate/replay identity와 exact replay, canonical equity session/NAV 일치, UTC timestamp 순서와 XNYS open/close 일치를 fail-closed로 검증합니다.
- sidecar는 원본 historical observation 또는 point-in-time 증거로 승격하지 않으며 readiness 기본값과 canonical artifact는 변경하지 않습니다.
- source path는 absolute regular file만 허용하고 symlink와 크기 초과를 거부하며, 생성 출력은 임시 파일에서 원자적으로 교체합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 내부 audit sidecar 계약만 추가했습니다.
- 운영 문서: 해당 없음. runner·서비스·주문 동작은 바꾸지 않았습니다.
- API·설정·데이터 계약: readiness 연결 없이 새 내부 Python entry point와 sidecar schema를 추가했습니다.

## 검증

- `PYTHONPATH=backend pytest -q backend/tests/test_research_canonical_time_evidence.py` — 3 passed
- `mypy --strict backend/jusik/research_canonical_time_evidence.py` — 통과
- `ruff check ...` — 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 주문, PAPER/live 승격, runner 재개, 원격 push 없음.
- canonical artifact는 읽기 전용으로 사용했습니다.

## 증거와 재개

- audit: `~/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/`; 생성 sidecar 경로는 호출자가 지정합니다.
- 남은 작업·차단 조건: sidecar는 calendar-derived technical evidence일 뿐 historical PIT
  observation proof가 아닙니다. readiness missing code 제거와 경제 acceptance는 별도 승인
  작업에서 판단합니다.
- 다음 시작: canonical sidecar verifier를 readiness에 연결할지 별도 계획·검증 작업으로
  결정하되, KOFR risk-free evidence와 기존 자료 completeness gate를 유지합니다.
