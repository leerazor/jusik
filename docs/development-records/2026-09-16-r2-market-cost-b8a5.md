# R2-02 시장 비용 독립 진단

- 상태: 차단 (기술 slice; 경제 not-evaluated)
- 기록 시각: 2026-09-16T00:00:00Z
- 작업 slug: `r2-market-cost-b8a5`
- 기준/통합: `baa192591a4ccf9a8cc9a21623ca075bacc8acc3` / 없음
- 범위: 독립 Decimal 비용 재계산, 고정 16개 시나리오, 저장 US 파일럿 bounded CLI와 계약 문서를 추가했습니다. 전략·shared model·주문·서비스·설정은 변경하지 않았습니다.

## 변경과 결정

- `market_cost_diagnostics.py`는 정밀도 28에서 KRW/USD 매수·매도 체결가, 체결금액, fee, 매도세, slippage, 현금 변동을 계산하고 저장값을 대조합니다.
- 고정 파일럿 SHA와 252 세션·106 거래 상한/동등성 검사를 CLI에 두었습니다. 실제 체결 timestamp·부분체결·취소·거절·주문 식별자는 저장 근거가 없어 unavailable로 기록합니다.
- 고정 시나리오는 KR buy/sell, US buy/sell, zero, negative, missing, duplicate, rounding, holiday, timezone, partial, cancelled, rejected, missing chronology, stored mismatch의 16개입니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-cost-diagnostics.md`에 계산식, CLI와 증거 한계를 기록했습니다.
- 운영 문서: 해당 없음. 네트워크·서비스·DB·주문 운영을 추가하지 않았습니다.
- API·설정·데이터 계약: 새 public API나 설정은 없으며 저장 run 입력만 읽습니다.

## 검증

- `PYTHONPATH=. .venv-r2/bin/python -m pytest tests/test_market_cost_diagnostics.py -q` — 19 passed, 0.18s, exit 0.
- `.venv-r2/bin/python -m ruff check jusik/market_cost_diagnostics.py tests/test_market_cost_diagnostics.py` — passed, 0.02s, exit 0.
- `.venv-r2/bin/python -m ruff format --check jusik/market_cost_diagnostics.py tests/test_market_cost_diagnostics.py` — passed, 0.01s, exit 0.
- `.venv-r2/bin/python -m mypy --strict jusik/market_cost_diagnostics.py tests/test_market_cost_diagnostics.py` — passed, 0.10s, exit 0.
- `git diff --check HEAD^ HEAD` — passed, 0.00s, exit 0.
- 저장 US 파일럿 CLI — `blocked`; frozen SHA 일치, 252 세션·106 거래, 저장값 mismatch 0, 출력 49,572 bytes. totals는 buy fee `27.221555102124220260047625`, sell fee `25.720489058519236602343005`, sell tax `308.64586870223083922811606`, slippage `352.9373069013059138308`, cash delta `-10368.69487022943201412130668`입니다.
- 초기 검증 이력: 환경에 Ruff 실행 바이너리가 없어 `python -m ruff` 두 명령이 exit 1이었고, 바이너리를 복사한 뒤 해결했습니다. 첫 pytest는 분류 오류로 실패했으며 수정 후 19 passed, 첫 strict mypy는 2개 타입 오류 후 수정했습니다. 실패를 성공으로 덮지 않았습니다.
- 실행하지 않은 검사: 네트워크 수집, simulation/replay, GPU, DB, 서비스, PAPER/live, 실제 주문.

## 안전·운영 상태

오프라인 CPU 산술만 수행합니다. 원본 파일을 수정하지 않으며 broker API·주문·운영 DB·서비스·remote push·live/PAPER 변경은 없습니다. 법정 세율·세목·유효기간·공식 근거는 unavailable이므로 경제적 결론을 내리지 않습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-02-b8a573f2/worker`; manifest: 기존 동결 입력 검증 자료.
- 남은 작업·차단 조건: 거래소 calendar, 체결 timestamp와 주문/부분체결 상태, 법정 세목·관할·유효기간·공식 요율 근거가 필요합니다. R2-02 전체 checkbox는 유지합니다.
- 다음 시작: 저장 입력 SHA와 전용 검증 로그를 먼저 확인한 뒤 독립 review 및 local main 통합 검사를 수행합니다.
