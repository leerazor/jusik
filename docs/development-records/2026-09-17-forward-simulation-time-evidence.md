# 전진 simulation 시간 근거

- 상태: 진행 (구현 브랜치; Astra 통합 전)
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `forward-simulation-time-evidence`
- 기준/구현: `a5746f7961172f060bfdb1dcfe8e759598eeb7ba` / 미정
- 범위: 기존 engine·simulation/result/run/replay schema를 바꾸지 않고 새 시간 근거 모델, opt-in offline bundle adapter/verify CLI, 계약 문서를 추가합니다.

## 변경과 결정

- `research_portfolio_time_models.py`는 initial-capital engine event anchor와 NAV별 close/session 연결을 strict versioned Pydantic 모델로 정의합니다.
- `research_portfolio_time_evidence.py`는 `_instrument_data`/`_events`를 먼저 고정하고 public `simulate`를 한 번 호출해 새 bundle만 생성합니다. verify는 engine을 호출하지 않습니다.
- 공식 session close보다 engine close가 앞서면 warmup를 포함해 fail-closed하며, NAV의 원래 `evaluation_at`과 시장별 session 시각을 분리해 보존합니다.

## 문서·계약 영향

- 사용자 문서: `docs/forward-simulation-time-evidence.md`에 생성/검증 계약을 기록했습니다.
- 성과 지표 문서: `docs/market-performance-metrics.md`에 sidecar 링크와 historical 소급 금지를 추가했습니다.
- API·설정·데이터 계약: 기존 API/readiness/run 저장소는 변경하지 않았고 새 bundle 경로에만 적용됩니다.

## 검증

- `pytest -q tests/test_research_portfolio.py tests/test_research_market_calendar.py` — 29 passed.
- `ruff check`, `ruff format --check`, focused strict `mypy` — 통과.
- 실제 연구/network/broker 주문은 실행하지 않았습니다.

## 안전·운영 상태

- PAPER/live, 실제 주문, 운영 DB·서비스·remote 변경 없음.
- fixture와 caller-provided calendar만 허용하며 manifest/파일 SHA와 새 출력 경로를 검증합니다.

## 증거와 재개

- audit: 없음; 이 작업은 합성 fixture focused 검증만 수행했습니다.
- 남은 작업: focused time-evidence 테스트와 독립 review, Astra main 통합 검증.
- 다음 시작: 새 adapter의 synthetic bundle generation/verify 및 tamper/causality 회귀를 실행합니다.
