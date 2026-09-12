# 다음 포트폴리오 개발 선택: 보유 밴드 상호작용

작성일: 2026-09-12 (한국 시각)

이번 문서는 연구를 실행한 보고서가 아니라 다음 실행 하나를 선택하는 등록 문서다. 선택할 successor는 `portfolio-held-band-interaction-v1` 하나다. 목표는 미보유 진입을 보정한 corrected-entry 규칙에서 보유 종목의 재배분 밴드를 2%p와 4%p로 비교하는 것이다. 기존 원본 2%p·4%p 결과와 corrected-entry 2%p 결과가 있으나 corrected-entry 4%p 결과는 아직 없다. 따라서 이 작업은 후속 가설을 새로 찾거나 승자를 고르는 작업이 아니라, 이미 고정된 상호작용의 빈 한 칸을 채우는 작업이다.

## 선택 근거

원본 밴드 연구에서 4%p는 연속 구간 거래 수를 171건에서 62건으로 줄이고 최대 낙폭을 7.37%에서 4.17%로 낮췄지만, 누적 수익률은 16.33%에서 10.01%로 낮아졌다. 비용 2배에서도 수익률은 14.99%에서 9.12%, 최대 낙폭은 7.51%에서 4.43%가 되었다. 7개 독립 fold의 4%p−2%p 수익 차이 중앙값은 비용 1배 −0.56%p, 비용 2배 −0.44%p였다. 이 결과만으로 보유 밴드 정책의 효과를 설명할 수 없다. 원본 규칙은 현재 보유 수량이 0인 양수 목표 진입도 밴드에서 생략할 수 있기 때문이다.

corrected-entry 2%p를 기준으로 보유 밴드만 4%p로 바꿔야 미보유 진입 보정과 보유 재배분 억제를 분리할 수 있다. 비용·회전율·최종 순자산을 함께 보고, 4.237%와 3.958%라는 robustness 수치는 각각 fold 수익률 중앙값인 점을 유지한다. 두 값의 차이 0.279%p는 중앙값의 차이이며, 비용 2배에 따른 selected 수익률 감소의 paired fold 차이 중앙값 0.223%p와 같은 통계량이 아니다. fold를 서로 연결해 복리나 하나의 연속 수익률로 만들지 않는다.

배분·순수익·회전율·강건성을 함께 해석한다. 보유 밴드가 넓어져 회전율과 거래비용이 줄어도 순수익 또는 fold별 수익 안정성이 악화될 수 있으며, 낙폭 감소만으로 승자를 선언하지 않는다. 4.237%/3.958%의 `selected_base`/`selected_cost_2x` 수치는 비용 1배/2배의 selected fold 수익률 중앙값이고, 최대 fold MDD는 각각 5.387%/5.464%였다. 이는 다음 실험의 사전 승자 기준이 아니며, 후속 결과가 음수여도 그대로 보고한다.

대기열에서 이미 완료된 `portfolio-symbol-removal-attribution-v1`과 `portfolio-exposure-cost-tradeoff-v1`는 입력 해석을 보강하지만 새 실행을 대신하지 않는다. 종목 제거 결과는 사후 고정자본 산술 민감도이고 인과적 제외 효과가 아니며, 노출·비용 진단은 실제 체결과 고정체결 산술을 구분한다. 이 선택은 그 연구들을 재실행하거나 backlog 전체를 다시 검토하지 않는다.

## 고정 입력과 근거

다음 파일을 읽기 전용으로 고정하고, 실행 전 바이트 SHA-256을 검증한다.

| 입력 | SHA-256 |
|---|---|
| `/home/kwl/.local/share/jusik/portfolio-audit/20260911T060908Z-rebalance-band/source-manifest.json` | `1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825` |
| `/home/kwl/.local/share/jusik/portfolio-audit/20260911T060908Z-rebalance-band/source-result.json` | `db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca` |
| `/home/kwl/.local/share/jusik/portfolio-audit/20260911T060908Z-rebalance-band/robustness-control.json` | `a6881452b4a87512761e6d3ddf467188f1795811c313be6237584ddc054bd3ef` |
| `backend/jusik/research_portfolio_engine.py` | `8790405075a22548f7490c8d4cced8845d3067cba647568a2169a908fe339ed2` |
| `backend/jusik/research_portfolio_models.py` | `e1fda47a0dc4cb37e4186b778d902cd293e6e2ec1fbd1be2b367bb967c865024` |
| `backend/jusik/research_external_features.py` | `d44346d43ebc00f18381058ad649e944bb022e6a3868d2f38a8c5edbec49e572` |
| `backend/jusik/research_risk.py` | `8e79dfa98defec7c9f28fcb8d035e5662903f229f3d6b80997b98b3773f88fcc` |
| corrected-entry source `backend/jusik/research_unheld_entry_experiment.py` | `a31a455ae79dddce3b19248bc85a4068be49d0d7d0f06bea50422818b866f6d8` |
| 원본 band 참고 runner `20260911T060908Z-rebalance-band/run_experiment.py` | `a7ef85a8b9633c3ffc956ca34600f215eae272654466be702f769fe04f698545` |
| corrected-entry 2%p `unheld-entry-real32/results.json` | `5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4` |
| corrected-entry specification `unheld-entry-real32/preregistration.json` | `9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7` |
| `prespecified.json` | `9e5159061a0d53e84bf2ad32ab1fc6b16e00497be557f51417cc9b8d63b56dd3` |
| `results.json` | `919fa270fa6192fc26d12cd2a631cb6128eec1cf42bfa325a8912f728d49edb1` |

선행 작업의 완료 JSON과 전체 evidence hash 검증은 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17/prerequisite-verification.json`에, 위 입력 목록은 `frozen-input-verification.json`에 보존되어 있다. 두 선행 작업은 모두 `runner_completed=true`, `all_hashes_verified=true`, `main_ancestor=true`다. 실행 전 이 두 JSON 자체도 읽어 선행 완료 상태를 확인한다.

고정 후보는 `portfolio_inverse_volatility_fx_vix_v1`, 정책은 `low_turnover_combined`, 초기 자본은 100,000,000 KRW다. 기간은 기존 `fold_1`~`fold_7`과 `continuous`를 그대로 사용한다. 각 fold는 독립적으로 초기화하며 fold 수익률을 합성하지 않는다. warmup 120, validation 40, signal 20, volatility/momentum/correlation 60, external max age 7일, reentry cooldown 28일, recovery confirmations 2, recovery minimum assets 2, volatility target 0.10, annualization 252, low-turnover weeks 4를 고정한다. `drawdown_limit=0.10`, `gross_cap=0.60`, `symbol_cap=0.20`, `leveraged_etf_cap=0.20`과 나머지 설정도 보존한다. 특히 `symbol_cap=0.20`은 변경하지 않는다.

비용은 `cost_multiplier=1,2` 두 개다. 배수 1은 fee/slippage/fx spread 각 0.001, 배수 2는 각 0.002다. corrected-entry 2%p control은 `/home/kwl/.local/share/jusik/portfolio-audit/20260911T132132Z-worktree-development/unheld-entry-real32/simulations/`의 `{fold_1..fold_7,continuous}-variant_c{1,2}.json` 16개 corrected simulation을 재현한다. root의 zero simulation이나 같은 디렉터리의 `*-b2_c*.json` 원본 control을 corrected baseline으로 사용하지 않는다. `research_unheld_entry_experiment.py`는 runner/helper source이고, 원본 `run_experiment.py`는 참고용 원본 band 결과다. 새 runner는 frozen `research_portfolio_engine.py`에 `_copy_engine`을 적용해 하나의 `variant_engine.py`를 만들고, `engine_variant_sha256=7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442`를 검증한다. 2%p와 4%p는 같은 corrected engine copy를 validated config로 실행하며 band 값만 다르다. 미보유 양수 목표 진입의 보정은 양쪽 arm에 동일하게 적용하고, 보유 양수 목표의 현재 비중−목표 비중 절대차가 band 미만이면 생략한다. 목표 0 청산과 한도 초과, 위험 청산은 band를 우회한다. 실제 진입은 신호, 현금, 정수 수량, 가격, 환율, cap 검사를 그대로 거친다.

선행 corrected-entry 2%p의 continuous 관측값은 control 171 trades, turnover 462.185415584%, final PnL 16,326,812.4745 KRW이고 variant 308 trades, turnover 569.592235285%, final PnL 27,863,943.6756 KRW다. 비용 2배 variant는 313 trades, final PnL 26,210,019.347 KRW다. 이 값은 successor의 새 결과가 아니라 저장된 historical prerequisite다. 종목 제거 attribution에서는 7 strict flips가 모두 `fold_1`에 있었고, cost 2 COHR의 예시는 −14,851.0708→218,971.9766 KRW였다. 이는 사후 산술 민감도이며 보유 밴드 효과나 인과 효과가 아니다.

수치 추적은 [entry attribution](../research-entry-attribution.md), [portfolio robustness](portfolio-stress-robustness-v1.md), [symbol removal attribution](portfolio-symbol-removal-attribution-v1.md), [exposure-cost tradeoff](portfolio-exposure-cost-tradeoff-v1.md)와 durable `selection-evidence-values.json`(`/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17/selection-evidence-values.json`)에서 확인한다.

입력은 재사용된 historical 자료이며 frozen prerequisite의 `point_in_time_verified=false`, `prospective_validation_eligible=false` 상태를 유지한다. synthetic time-order fixture는 실행 경로의 누출 방지만 검증하고 historical source의 point-in-time 정확성을 인증하지 않는다. 배당·분배금, 생존·상장 편향, 원천 자료의 시각·완전성 한계는 남아 있다. 결과는 정책 승격, PAPER 활성화, 실거래 적합성을 의미하지 않는다.

## 실행 범위와 산출물

후속 구현은 다음 세 파일과 고정된 실행 전용 audit 산출물만 만든다.

- `backend/jusik/research_portfolio_held_band_experiment.py`: frozen `research_portfolio_engine.py`에 기존 `_copy_engine`/`_load_copy`/guard 패턴을 적용해 하나의 `variant_engine.py`를 구성하는 bounded runner. validated model로 band만 0.02/0.04를 주입하고, corrected-entry 보정·나머지 엔진·설정의 의미는 보존한다. `engine_variant_sha256`를 검증하며 제품 엔진을 monkeypatch하지 않는다.
- `backend/tests/test_research_portfolio_held_band_experiment.py`: 아래 합성·회귀·회계 테스트.
- `docs/research/portfolio-held-band-interaction-v1.md`: 실행 결과와 실패·음성 결과를 기록할 successor 보고서. 선택 문서는 실행 후 덮어쓰지 않는다.

총 실행 한도는 `8 periods × 2 cost multipliers × 2 corrected arms = 32 simulations`이다. arm은 corrected-entry 2%p control과 corrected-entry 4%p variant다. 결과 디렉터리는 신규·전용 durable audit 경로로 만들고, 기존 결과를 덮어쓰지 않는다. 각 simulation JSON, `results.json`, `results.csv`, prespec, source copy diff/hash, 입력 manifest, 회계 검증, 환경과 실행 로그를 보존한다. 실행 중 오류가 나면 부족한 결과를 성공으로 포장하지 않고, 실패한 period/arm/cost와 원인, 이미 생성된 모든 출력의 경로·SHA를 기록한다. 일부 성공만으로 정책 승격이나 재실행 범위 확대를 하지 않는다.

대조군 16개는 잠긴 corrected-entry 2%p 전체 결과의 `PortfolioSimulation.model_dump(mode='json')`와 metrics, trades, events를 포함해 exact equality여야 한다. control replay가 실패하면 4%p 비교를 해석하지 않고 실패로 종료한다. Decimal 회계 reconciliation에만 `0.000001 KRW` 이하 허용오차를 적용하며 control 비교에는 허용오차를 적용하지 않는다. 결과 표에는 period, arm, cost, total return, MDD, trade count, turnover, transaction cost, FX cost, actual unheld entry count, band skip count, completion과 failure reason을 모두 기록한다. 진단 행은 설명 자료이며 후보 동등성 또는 승자 조건으로 사용하지 않는다.

## 검증 계약

합성 엔진 fixture는 다음을 모두 확인한다.

- 미보유 종목의 양수 목표는 2%p/4%p 모두 진입 검사를 거쳐 band에 의해 생략되지 않는다.
- 보유 종목의 목표 차이가 band보다 작으면 생략되고, 정확히 0.02 및 0.04는 사전 정의한 경계 규칙대로 처리된다.
- 목표 0 청산, `symbol_cap=0.20` 초과, 위험 청산은 band와 무관하게 실행된다.
- 목표 0, 음수 목표, 누락 입력, 중복 행, `NaN`·`Infinity` 같은 비유한 값은 거부 또는 명시된 zero 처리로 일관되며 조용히 통과하지 않는다.
- 0 값과 음수 금액, 가격·환율 누락, 중복 시계열을 검증한다. 금융값은 Decimal로 계산하고 반올림·정수 수량·최소 체결 조건을 확인한다.
- 시장 휴일과 조기 폐장, UTC 저장 및 표시 시간대 경계, 다음 유효 개장 체결을 확인한다. 결정 시각까지 이용 가능한 feature만 읽으며, 다음 유효 개장 체결 가격은 결정 이후 실행을 시뮬레이션하기 위해 합법적으로 사용한다. 결정 이후의 feature를 의사결정에 읽어 미래를 누출하지 않는다.
- 부분 체결·취소·거절은 기존 receipt/execution 의미와 회계 처리를 그대로 보존한다. 이 문서와 테스트는 그런 이벤트를 새로 발명하거나 성공 체결로 가장하지 않는다.
- 현금, 보유 평가액, 체결 notional, fee, slippage, FX cost, transaction cost, 최종 자산, 초기 자본, 저장 contribution의 reconciliation을 Decimal 허용오차 안에서 확인한다. 거래 수·비용·회전율·최종 순손익과 종목 귀속 합계를 대조한다.
- corrected-entry 2%p control 16개 전체를 재생해 `PortfolioSimulation.model_dump(mode='json')` 전체와 metrics, trades, events의 exact equality, 회계·미래 누출 검사를 통과시킨다. 저장된 16개 corrected simulation과 전체 결과를 비교하고, 합성 fixture와 직렬화 출력의 결정성을 반복 확인한다. 결과 비교는 fold별로 수행하며 fold와 continuous를 합산하지 않는다.

다음 판정은 사전 등록한다. 32개가 모두 complete이고 control replay가 일치하며 회계·입력 hash·누출 검사가 모두 통과해야 비교 결과를 해석한다. 4%p가 수익률, MDD, 비용 또는 회전율 중 어느 하나에서 유리해도 다른 지표의 손실을 숨기지 않는다. robustness 중앙값은 fold별 단순 수익률의 중앙값으로만 보고한다. 원본과 corrected의 차이를 설명할 필요가 있을 때는 저장된 원본 결과와 corrected 결과의 차이의 차이를 기술통계로 계산할 수 있지만, fold와 continuous를 더하지 않고 인과적 효과라고 주장하지 않는다. 실행 결과가 음수이거나 기준을 충족하지 않으면 그 부정 결과를 종료 조건으로 보존하며 retuning, winner selection, PAPER 설정 변경을 하지 않는다.

이번 선택 문서를 작성하는 동안 실험은 실행하지 않았다. 따라서 이 문서의 수치는 선행 고정 자료에서 인용한 값이며, successor가 실행되기 전에는 새 성과 주장으로 사용할 수 없다.

## 후속 작업 지시문

아래 prompt는 successor 담당자가 그대로 사용할 수 있는 실행 지시이며 2,000자 이내다.

```text
portfolio-held-band-interaction-v1을 실행하라. 목표는 corrected-entry 규칙의 보유 재배분 band 2%p 대 4%p 비교 하나다. backend/jusik/research_portfolio_held_band_experiment.py는 research_portfolio_engine.py에 _copy_engine/_load_copy/guard를 적용해 variant_engine.py 하나를 만들고 validated configs로 같은 corrected engine을 .02/.04에 재사용하라. engine_variant_sha256=7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442를 검증하라. tests/test_research_portfolio_held_band_experiment.py와 docs/research/portfolio-held-band-interaction-v1.md를 추가하라. 제품 엔진/DB/PAPER 설정은 수정하지 말라.

입력은 /home/kwl/.local/share/jusik/portfolio-audit/20260911T060908Z-rebalance-band의 source-manifest.json, source-result.json, robustness-control.json과 /home/kwl/.local/share/jusik/portfolio-audit/20260911T132132Z-worktree-development/unheld-entry-real32/results.json, preregistration.json, simulations/{fold_1..fold_7,continuous}-variant_c{1,2}.json 16개다. root의 zero simulation과 `*-b2_c*.json` original control은 쓰지 말라. corrected source와 파일 SHA-256을 확인하라. 모든 frozen config, drawdown_limit=.10, symbol_cap=.20을 보존하고 1x/2x·2pp/4pp 정확히 32회만 실행하라. 2pp control은 저장된 각 PortfolioSimulation.model_dump(mode='json') 전체(metrics/trades/events 포함)와 exact equality여야 하며 control 비교에는 tolerance가 없다. Decimal reconciliation만 <=1e-6 KRW다.

검증: unheld/held/zero target, 정확히 .02/.04 경계, cap/risk exit, zero·negative·missing·duplicate·nonfinite 입력, 휴일/UTC 경계, rounding, decision feature cutoff와 next-open 실행, partial/cancel/reject 의미와 Decimal 회계를 확인하라. 각 결과와 실패 원인·모든 산출물 hash를 durable audit에 보존하라. fold를 합치거나 continuous와 합산하지 말고, retuning/winner selection/PAPER 반영, remote push/refetch, runner/GPU 변경을 하지 말라. 원본과 corrected 차이의 차이는 기술통계로만 보고 인과 주장하지 말라. 실행 후 successor 문서에 결과·음성 결과·남은 실패를 추가하고 테스트·Ruff·strict mypy를 기록하라. 그 뒤 broader portfolio engineering gaps를 evidence로 inspect하고, 이 목표 직후 실행 가능한 successor scope/tests를 최대 하나만 제안하라. backlog review를 후속으로 제안하지 말라.
```

더 넓은 공백을 이어서 찾더라도, 이 목표가 끝난 뒤에는 고정 입력·재현 가능한 실행 경로·필수 회계/누출 테스트를 갖춘 evidence-backed successor scope를 최대 하나만 제안하라. backlog 전체를 재검토하거나 실행 범위를 늘리지 말라.
