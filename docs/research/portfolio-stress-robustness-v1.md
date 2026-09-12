# 포트폴리오 스트레스 강건성 검토

## 범위와 재현

기준 커밋 `29c5327768e298a284171cce8ec933e1a274ed29`, 작업 기준 `a7e18e7`에서 기존 오프라인 검증 경로를 사용했다. 입력 source run은 `c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0`이다. 선택은 각 OOS 구간보다 먼저 수행하고, 각 fold를 현금 1억원으로 독립 초기화한다. 7 folds, fold당 최대 21개 후보·조건, 논리 평가 최대 147회를 적용했다. 비용 민감도는 2배이며 `signal_window` 15/25, `volatility_window` 45/75를 한 번에 하나씩 바꿨다.

```bash
cd /home/kwl/projects/jusik/backend
.venv/bin/python -m jusik.research_portfolio_robustness \
  --source-report-dir /home/kwl/.local/share/jusik/research-universe-reports \
  --report-dir /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0/replay
```

재현 출력은 attempt 전용 audit 경로에 보존했다. `run_id=d10af7147507692900de0b45323cef7deed90642ede284a5f301cdc9cf7c0ff6`, 계산 완료, 7/7 fold 완료, 논리 평가 147회, union dates 774개다. 미사용 tail은 2026-08-20~2026-09-08, 14일이다.

고정 해시는 다음과 같다.

| 항목 | SHA-256 |
|---|---|
| source manifest | `1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825` |
| source result | `db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca` |
| robustness code | `c6af044d05090cacb8c685ae7ee7044752cfdeb46486b07049d2af1a4edb9f9a` |
| specification | `03fb212ced6332fdc67256df6bd6932a97a7f7be6a46de3277762e16636cf0f1` |
| replay result | `e2a9b62dbd72df2ed906c21de520a8951b0b29c16c3012c028fd6389384e6332` |
| replay folds | `d37badfa2f0cea3acd874bd92c5484cca241eeaf933d9db7d2f6788d5606e612` |
| replay validation | `27c98ca2806a4606ab7967b5cd5d791089e2eb95cda9a98e1a454a2427d066d7` |
| replay sensitivity | `79fe198b78251e5eea2ae8bec58f4ae5ade1ba2de8d3aa0932507b1f8f568a42` |
| replay report | `f762363056f62df3a8c0e313bd38fa6d78ede6c424c936dfaccb72024a5d7c10` |

## 결과

수익률은 fold별 단순 수익률(%)이며, 중앙값과 최악 fold를 함께 기록한다. MDD는 fold 중 최대값이다. fold 수익률을 연결해 전체 기간 복리나 연율 수익률로 해석하지 않는다.

| 조건 | 중앙값 수익률 (%) | 최악 fold (%) | 최대 fold MDD (%) |
|---|---:|---:|---:|
| equal_baseline | 1.174 | -3.505 | 5.180 |
| fixed_base | 1.219 | -3.649 | 5.244 |
| fixed_cost_2x | 1.059 | -3.829 | 5.324 |
| selected_base | 4.237 | -2.542 | 5.387 |
| selected_cost_2x | 3.958 | -2.652 | 5.464 |
| signal_window_15 | 2.568 | -3.681 | 5.244 |
| signal_window_25 | 1.525 | -2.982 | 4.822 |
| volatility_window_45 | 2.232 | -3.564 | 5.108 |
| volatility_window_75 | 1.539 | -3.721 | 5.292 |

선택 전략은 7개 fold 중 4개에서 equal baseline을 상회했고, 고정 전략은 3개에서 상회했다. 비용 2배의 fold 수익률 감소 중앙값은 selected 0.223%p, fixed 0.165%p다. 모든 fold에 거래가 있었고, 결과는 후향 검증 요약이다.

## 해석과 제한

고정된 과거 자료를 반복 사용한 검토이며 새로운 holdout이 아니다. 생존편향, 배당, 상장 시점과 원천 자료의 한계를 해소하지 않는다. 수익성, 실거래 적합성 또는 자동 승격을 승인하지 않는다. PAPER 엔진·DB, 주문, GPU, 원격 push와 엔진 코드는 변경하지 않았다.

미래 평가 구간 2026-09-14~2026-11-09는 사전등록된 `research_prospective_registration` 계약에 속한다. 계약 identity는 source run `fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687` 및 등록된 session·policy·code/calendar hash로 고정한다. 이 historical robustness CLI와 고정 source를 미래 입력으로 재사용하지 않는다. 계약 기간이 끝난 뒤에는 `[start, end)` 수신 구간의 fill provenance와 실제 시작·종료 raw boundary artifact를 확인하고, 경계 NAV가 승인되고 `evaluation_inputs_complete=true`일 때만 계약 정의에 따라 별도 PAPER 평가를 산출한다. 현재는 경계 NAV/evidence와 완료된 prospective 표본이 없어 검증이 차단된다. 기준 시점 보존 자료의 readiness 상태는 현재 수집기 상태나 미래 성과의 증거가 아니다.

## 검사와 보존

기준 상태에서 `test_research_validation.py`와 `test_research_portfolio.py`는 31 passed, 기존 deprecation warning 2건이었다. robustness 모듈 Ruff check/format 및 strict mypy도 통과했다. 통합 후 검사는 Astra가 수행한다. frontend 변경이 없어 build는 해당하지 않는다.

모든 replay 산출물과 source hash 근거는 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0/replay/` 및 해당 attempt audit 디렉터리에 보존한다. 독립 review, SHA-256 index, handoff와 통합 검증이 끝나기 전에는 완료로 표시하지 않는다.
