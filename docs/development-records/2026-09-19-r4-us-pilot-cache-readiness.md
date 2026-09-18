# R4 미국 pilot cache readiness 재검증

- 상태: 자료 게이트 차단·pilot 미실행
- 기록 시각: 2026-09-19T01:20:00+09:00
- 범위: 기존 US approximate pilot cache를 read-only `collect-status`로 확인했습니다. 네트워크 수집, 연구 실행, 결과 덮어쓰기, PAPER/live와 주문은 수행하지 않았습니다.

## 검증

- 명령: `PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_research_cli collect-status --cache /home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/us-pilot-1y-stable-cache --market US --start 2025-09-11 --end 2026-09-11 --output /tmp/jusik-collect-status.json`
- 결과: cache entries `84`, `completed=false`, `ready=false`, exit code `2`
- 누락 자격증명: `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`
- 기존 cache checkpoint와 원본 artifact는 변경하지 않았습니다.

## 판정과 재개 조건

기존 frozen US pilot은 independent cost/NAV 검증을 통과했지만, 현재 R4 pilot의 자료 readiness와 동일하지 않습니다. 따라서 기존 결과를 현재 policy의 새 pilot 또는 strict/PIT 근거로 재명명하지 않습니다. 누락 자격증명이 준비되거나 동일한 provenance를 가진 공급자 응답 파일이 제공되어 cache coverage·membership·FX·기업행동 계약을 다시 통과할 때만 bounded pilot을 실행합니다. 그 전에는 R4-01~R4-05와 경제 승격을 보류합니다.
