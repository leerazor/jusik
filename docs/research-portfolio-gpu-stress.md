# GPU 포트폴리오 경로 스트레스

이 도구는 보관된 `PortfolioSimulation`의 연속 NAV 경로를 관측값 단위 블록 부트스트랩으로 재표본화한다. 실제 주문, PAPER/live 엔진, DB, daemon, 시세 수집을 호출하지 않으며 NAV에 이미 포함된 비용과 통제를 다시 적용하지 않는다. 입출금이 없다는 해석은 검증된 원본 실험 계약에 의존하며 NAV와 SHA만으로 입출금 흐름을 증명하지 않는다.

## 입력 계약

```json
{
  "cases": [
    {"name": "control", "path": "/readonly/control.json", "sha256": "64 hex"},
    {"name": "variant", "path": "/readonly/variant.json", "sha256": "64 hex"}
  ],
  "initial_capital_krw": "100000000",
  "seed": 20260913,
  "block_length_observations": 20,
  "scenarios": 512,
  "horizon_observations": 1171
}
```

`cases`는 1~4개의 독립된 named NAV path다. 각 파일은 지정 SHA와 일치하는 complete `PortfolioSimulation`이어야 하며 source는 2~1,172개 NAV point를 제공한다. NAV는 유한·양수이고 timestamp는 중복 없는 strict UTC chronological sequence여야 하며 모든 case의 timestamp 배열은 정확히 같아야 한다. source final NAV·MDD·return metadata는 Decimal 기준으로 재계산해 검증하며 요청에 중복 선언하지 않는다. horizon은 return observations 기준 최대 1,171, scenarios는 최대 4,096이다.

## 실행

```bash
python -m jusik.research_portfolio_gpu_stress \
  --request request.json --output-dir /tmp/gpu-stress-run --device auto
```

`auto`의 현재 `scenarios >= 512` CUDA 선택은 측정된 speedup이 아닌 규모 휴리스틱이다. 512 scenario smoke 측정에서는 CPU가 더 빠를 수 있다. `cuda`는 torch/CUDA가 없거나 메모리·parity 검증에 실패하면 CPU로 바꾸지 않고 명시적으로 실패한다. CUDA와 torch CPU 경로는 float64 batched `cumprod`/`cummax`를 사용하고 initial capital을 peak에 포함한다. CPU Decimal 계산이 authoritative output과 20% 경계 분류를 판정하며 torch 결과는 허용 오차 parity를 검증한다. 생성된 indices는 모든 case와 backend에서 공유한다.

출력은 `request.json`, `preregistration.json`, `indices.json`/`indices.sha256`, `results.json`, `summary.json`, `report.md`, `hash-manifest.json`, `environment.json`이다. 새롭고 비어 있는 일반 디렉터리만 허용하며 기존 결과·symlink·부분 실행을 덮어쓰지 않는다.

`loss_frequency`와 `drawdown_20_frequency`는 각각 별도의 생성 시나리오 빈도이며, `loss_drawdown_20_frequency`는 두 조건의 교집합이다. 모두 생성된 경로의 기술통계이며 미래 확률, 위험 실행, 후보 승격 또는 투자 권고가 아니다.

benchmark는 GPU warmup 뒤 synchronize를 포함한 end-to-end 실행 시간과 host/device transfer를 포함한다. CPU는 2·8 threads 각각 warmup 후 동일 계산을 측정하고 원래 thread 수를 복원한다. 입력 검증, Decimal 기준 계산, 출력과 hash manifest 작성 비용은 benchmark 시간에 포함되지 않으므로 hardware speedup으로 해석하지 않는다.
