# GPU 역할 전환

기존 `research_universe` 실행은 수집과 통합 포트폴리오 연구를 유지하면서 종목별 legacy optimizer를 선택적으로 건너뛸 수 있습니다.

```bash
cd backend
.venv/bin/python -m jusik.research_universe run --once --collection-only --device cpu
```

`--collection-only`는 Yahoo·KIS 주가 수집, 외부 자료 수집, `run_from_stores` 포트폴리오 연구, 보고서 작성과 기존 lock·heartbeat·SIGTERM 중단 처리를 실행합니다. 종목별 optimizer identity 계산, 결과 행 갱신, 후보 평가, PyTorch import와 device resolution은 실행하지 않습니다. 기존 optimizer 행은 보존됩니다. 이 옵션을 지정하지 않으면 기존 동작과 `--device auto|cpu|cuda` 의미를 그대로 사용합니다.

지속 수집 서비스 템플릿은 `deploy/systemd/jusik-research-optimizer.service`입니다. 설치와 service 변경은 운영자가 검토한 뒤 사용자 단위에서 수행합니다. 이 저장소는 서비스를 자동 설치하거나 실행하지 않습니다.

GPU는 요청 기반 포트폴리오 stress 실험에만 사용합니다. 실행기는 다음 CLI와 요청 파일을 사용하며, 입력·seed·bounds·CPU parity 조건을 요청에 고정해야 합니다.

```bash
.venv/bin/python -m jusik.research_portfolio_gpu_stress \
  --request PATH --output-dir PATH --device auto
```

`auto|cpu|cuda` 중 장치를 요청하고, approximate stress 결과를 PAPER 전략이나 실거래로 승격하지 않습니다. 일반 자동 연구 작업은 임의로 systemd service를 변경하지 않습니다.
