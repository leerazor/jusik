# R1 bounded US collection recheck

- 기록 시각: 2026-09-22
- 범위: 기존 frozen cache를 변경하지 않고 `.env`의 Alpha Vantage·FRED·SEC 설정을 사용한
  US 표본 3개, request budget 10회의 read-only collection.
- 명령:
  `PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_research_cli collect --market US --env-file .env --start 2025-09-11 --end 2026-09-11 --sample-size 3 --request-budget 10 --cache /home/kwl/.local/share/jusik/portfolio-audit/20260922-us-collection-r1-05/cache --output /home/kwl/.local/share/jusik/portfolio-audit/20260922-us-collection-r1-05/result.json`

## 결과

- 결과 상태: `insufficient`; 사유: `FRED FX observation unavailable before 2025-09-11 open`.
- Alpha Vantage 2개, Yahoo 1개, FRED 1개 원문이 secret-free cache에 저장됐습니다.
- FRED 응답은 관측값을 포함하지만 `realtime_start=2026-09-21`인 현재 vintage입니다.
  따라서 2025년 거래일 시점에 해당 환율이 공개됐다는 근거로 사용할 수 없습니다.
- 수집 결과를 historical PIT evidence·R1-05 coverage·경제 acceptance로 승격하지 않았습니다.

## 재개 조건

세션별 또는 기간별 historical FRED vintage/publication timestamp를 제공해 각 환율이 해당
미국 장 시작 전에 관측 가능했음을 증명해야 합니다. 현재 collector는 최신 vintage를 과거
시점에 소급하지 않으며, 누락 시 `insufficient`를 유지합니다.

Audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-collection-r1-05/cache/manifest.json`.
실주문·PAPER/live·simulation/replay·GPU·원격 변경은 수행하지 않았습니다.
