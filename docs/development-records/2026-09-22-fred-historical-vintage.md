# FRED historical vintage collection

- 기록 시각: 2026-09-22
- 목적: 최신 FRED vintage를 과거 세션에 소급하지 않고, historical FX를 당시 이용
  가능한 vintage로 구성합니다.

## 구현

- `market_data_collector.py`에 FRED vintage-date endpoint와 vintage observation 요청을
  추가했습니다.
- US collection은 가장 가까운 과거 vintage 1개와 이후 vintage들을 요청하고, 각 값의
  `available_at`을 vintage 다음 UTC 자정으로 보수적으로 설정합니다.
- 요청 전 estimate에 vintage-date 1회와 기간별 주간 vintage 요청 예산을 포함합니다.
- 기존 fixture transport는 기존 단일 FRED 경로를 유지하므로 오프라인 테스트 계약을
  깨지 않습니다.

## 실제 bounded 검증

명령:

`PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_research_cli collect --market US --env-file .env --start 2025-09-11 --end 2026-09-11 --sample-size 3 --request-budget 70 --cache /home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-2/cache --output /home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-2/result.json`

- 결과: `collected`; 62 cache entries, bars 272, FX 272, 제외 심볼 2개.
- 별도 검산에서 FX 272행 모두 `available_at <= NMS session open`이며 위반 0건입니다.
- 이 결과는 approximate 자료입니다. 기업행사 전체 coverage·benchmark·미래 검증이 없으므로
  경제 성과 acceptance나 PAPER/live 승격 근거로 사용하지 않습니다.

## 검증

- collector pytest: `146 passed`
- Ruff check: 통과
- 변경 모듈 mypy: 통과
- `git diff --check`: 통과
- 전체 파일 Ruff format check에는 기존 포맷 부채가 남아 있으며 이번 변경으로 새 파일을
  포맷 전체 재작성하지 않았습니다.

Audit cache: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-2/cache/manifest.json`.
