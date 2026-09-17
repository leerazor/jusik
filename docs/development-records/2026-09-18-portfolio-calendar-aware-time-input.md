# portfolio calendar-aware time input

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-calendar-aware-time-input`
- 기준/통합: `0805c7a07b004d7a53a53b0946c21e7b8a8aa12e` / 통합 전
- 범위: portfolio engine의 opt-in 공식 session timing, time-evidence 실행 정책과 bounded lexical JSON 한도를 구현했습니다. legacy 결과·bundle shape와 일반/PAPER 호출은 보존했습니다.

## 변경과 결정

- `research_portfolio_engine.py`는 keyword-only `calendar`를 public simulate과 내부 target/event/volatility 경로에 전달합니다. 공식 경로는 모든 bar와 warmup를 session 존재·coverage 기준으로 먼저 검증하고, 불변 `InstrumentData` session timing을 event와 causal history 계산에 공유합니다.
- `research_portfolio_time_evidence.py`는 `legacy` 기본과 `official` 정책을 구분합니다. legacy config에서 새 필드를 직렬화하지 않고 기존 manifest 키를 보존하며, official manifest는 정책과 현재 engine source SHA-256을 고정합니다. 검증은 simulation을 호출하지 않습니다.
- `verify_bundle()`도 calendar bytes를 동일한 strict JSON pre-parser로 통과시켜 lexical/depth/collection bounds 우회를 차단합니다.
- lexical JSON 상한만 400,000으로 올리고 기존 bytes/total/depth/object/list/duplicate/nonfinite/regular-file 제한은 유지했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/forward-simulation-time-evidence.md`에 정책·identity·bounded 입력 계약을 기록했습니다.
- 운영 문서: 해당 없음. runner/network/service/PAPER/live/order/DB 설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 새 execution policy는 time-evidence adapter와 official bundle에만 적용되고 legacy 입력은 누락 필드로 계속 읽힙니다.

## 검증

- `PYTHONPATH=. .venv/bin/python -m pytest tests/test_research_portfolio.py tests/test_research_portfolio_time_evidence.py tests/test_research_market_calendar.py tests/test_research_forward.py -q` — 64 passed.
- 합성 source에서 legacy/official direct simulation equality 및 official bundle generate/verify round-trip — 통과.
- `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-aware-time-input/run-tYFlwC/result` fixed input parser/event-plan preflight — 통과; simulation 호출 0회, 0.744887초, max RSS 105620 KiB.
- `python -m py_compile` 대상 변경 모듈 — 통과.
- Ruff/mypy는 초기 환경에 도구가 없어 preflight 전 실행하지 못했으며, 전용 `.venv` 의존성 설치 후 실행합니다.

## 안전·운영 상태

- 실제 brokerage 주문, PAPER/live 실행, 네트워크 수집, 운영 DB·서비스·remote 변경은 없습니다. 고정 입력은 parser/event-plan까지만 읽었고 simulation/bundle은 생성하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-aware-time-input/run-Wro0bO/result`; manifest SHA-256 `7a2ddb3488d1bc08d155411122e8727c84a67db9b1150a3df7ef504acf207af4`
- 남은 작업·차단 조건: 이 워크트리 커밋과 Astra의 main 통합 검증이 남았습니다.
- 다음 시작: 변경 파일 diff와 Ruff/strict mypy 결과를 확인한 뒤 이 작업 브랜치를 통합합니다.
