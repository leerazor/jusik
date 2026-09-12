# GPU 포트폴리오 경로 스트레스

이 도구는 보관된 `PortfolioSimulation`의 연속 순자산가치(NAV) 경로를 관측값 단위 블록 부트스트랩으로 재표본화한다. 실제 주문, PAPER/live 엔진, DB, daemon, 시세 수집을 호출하지 않는다. 입력 NAV에 이미 포함된 control/variant 비용과 통제를 다시 적용하지 않는다.

## 입력 계약

```json
{
  "cases": [
    {"name": "continuous-control", "path": "/readonly/control.json", "sha256": "64 hex"},
    {"name": "continuous-variant", "path": "/readonly/variant.json", "sha256": "64 hex"}
  ],
  "initial_capital_krw": "100000000",
  "seed": 20260913,
  "block_length_observations": 20,
  "scenarios": 512,
  "horizon_observations": 1172
}
```

`cases`는 1~4개의 정확히 정렬된 NAV 경로다. 각 파일은 지정 SHA와 일치하는 complete `PortfolioSimulation`이어야 하며, NAV는 유한·양수이고 timestamp는 중복 없는 strict UTC chronological sequence여야 한다. 모든 case의 timestamp 배열은 정확히 같아야 한다. initial NAV와 source final/MDD/return metrics는 고정 파일에서 읽어 검증하며 요청에 중복 선언하지 않는다. horizon은 return observations 기준 최대 1,171, scenarios는 최대 4,096이다. 날짜나 calendar day로 집계하지 않는다.

## 실행

```bash
python -m jusik.research_portfolio_gpu_stress \
  --request request.json --output-dir /tmp/gpu-stress-run --device auto
```

`auto`는 작은 실행 또는 CUDA 미사용 시 CPU를 선택한다. `cuda`는 torch/CUDA가 없거나 메모리·parity 검증에 실패하면 성공한 것처럼 CPU로 바꾸지 않고 실패한다. CUDA 경로는 float64 batched `cumprod`/`cummax`를 사용하고 initial capital을 peak에 포함한다. CPU는 같은 persisted indices를 사용하며 20% 경계는 Decimal 계산으로 판정한다.

출력은 `request.json`, `preregistration.json`, `indices.json`/`indices.sha256`, `results.json`, `summary.json`, `report.md`, `hash-manifest.json`, `environment.json`이다. 새롭고 비어 있는 일반 디렉터리만 허용하며 기존 결과·symlink·부분 실행을 덮어쓰지 않는다.

terminal return, maximum drawdown, `terminal return < 0 and max drawdown >= 20%` 빈도는 생성된 역사 경로의 기술통계다. 예측 확률, 위험 실행, 후보 승격 또는 투자 권고가 아니다.
