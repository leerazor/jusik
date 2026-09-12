# 포트폴리오 종목 제거 산술 민감도

이 연구는 동결된 32개 simulation과 기존 `research_entry_attribution.analyze` 결과를 재검산한 뒤, 7개 fold와 continuous를 합산하지 않고 각각 종목 기여를 차감한다. 각 기간과 cost(1, 2)에 16개 종목을 모두 출력하며, 원래 팔에 없던 종목은 기여 0으로 명시한다.

계산은 `remaining_pnl = total_pnl - symbol_net_pnl`, `ratio = remaining_pnl / fixed_initial_capital`이다. 전후 우위는 `variant - control`이며, 부호는 원시 Decimal 값으로 판정한다. 양수↔음수만 `strict_flip`이고, 0 도달과 0 출발은 별도 상태다.

CLI는 `--input-dir`, `--saved-attribution`, `--output-dir`를 받는다. 저장 attribution의 SHA-256과 fresh 재계산을 대조하고, 결과 32개·16 pair·256 symbol 행의 완전성과 기존 회계 reconciliation을 요구한다. 출력은 결정적인 `concentration.json`, `concentration.csv`, `report.md`다.

실제 동결 입력 관측값은 다음 7건의 strict flip이다(금액 단위: KRW).

| 기간 | cost | 종목 | 제거 전 우위 | 제거 후 우위 |
|---|---:|---|---:|---:|
| fold_1 | 1 | 000660 | -27854.1501070847632106376359790002442 | 374507.4458929152367893623640209997558 |
| fold_1 | 1 | AMD | -27854.1501070847632106376359790002442 | 715.01264658497150469463287090209955000 |
| fold_1 | 1 | COHR | -27854.1501070847632106376359790002442 | 197147.96867578196384712359090072875970625 |
| fold_1 | 1 | SOXL | -27854.1501070847632106376359790002442 | 291635.908566651267761220358727353515565625 |
| fold_1 | 2 | 000660 | -14851.0708429977731907888934323730468 | 348459.1371570022268092111065676269532 |
| fold_1 | 2 | COHR | -14851.0708429977731907888934323730468 | 218971.97656513708043569791075584960945000 |
| fold_1 | 2 | SOXL | -14851.0708429977731907888934323730468 | 316230.974729257940438153333871777343825000 |

입력 SHA-256은 attribution `3955050f3d29ed42f64988a502705cdfff1c2591bfb084d0c7acb0050dd189d9`, results `5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4`다. 검증 명령은 `cd backend && .venv/bin/python -m pytest -q tests/test_research_portfolio_concentration.py`, `cd backend && .venv/bin/ruff check jusik/research_portfolio_concentration.py tests/test_research_portfolio_concentration.py`, `cd backend && .venv/bin/python -m mypy jusik/research_portfolio_concentration.py tests/test_research_portfolio_concentration.py`이며 실제 replay는 CLI를 동일 입력으로 2회 실행해 JSON/CSV/report 바이트를 비교했다.

관측된 strict flip은 fold_1에만 있었고, fold_2·fold_3·fold_4·fold_5·fold_6·fold_7 및 continuous에서는 strict flip이 없었다. tie 전이도 실제 동결 자료에서는 없으며, tie와 0 전이는 합성 fixture로 검증했다.

이 결과는 이미 실현된 경로의 고정 자본 사후 산술 민감도다. 자금 재배분이나 재시뮬레이션을 수행하지 않으며, 종목을 거래하지 않았을 때의 수익률·인과 효과·제외 권고를 뜻하지 않는다. PAPER 10% 운영 제한은 변경하지 않는다.
