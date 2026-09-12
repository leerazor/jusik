# PAPER 신호 동시 timestamp anomaly 에피소드

이 문서는 보존된 timestamp forensics 결과에서 같은 UTC 분에 두 종목 이상에서
관측된 anomaly를 집계한 재현 결과다. 입력은 보존된 anomaly CSV와 독립 재생
JSON이며, 분석기는 입력을 수정하지 않고 시작·종료 SHA-256을 대조한다.

`received_at - market_at`이 -2초보다 작거나 15초보다 큰 경우만 anomaly로
분류한다. 경계값은 strict 비교라서 정확히 -2초와 15초인 관측은 정상이다.
각 분에는 관측 symbol, anomaly symbol, 관측 정상 symbol, 결측 symbol 및
관측 symbol 분모를 기록한다. 행 ID와 중복 관측은 보존하고 symbol 집합만
중복 제거한다.

에피소드는 anomaly symbol이 두 개 이상인 분이 정확히 60초 간격으로 이어진
구간이다. 결측 또는 정상 분, session 경계, UTC 날짜 경계에서 에피소드를
분리한다. 고정 재생 결과는 선택 관측 6,164건, anomaly 249건, 동시 anomaly
분 68개, 최대 동시 symbol 5개, 에피소드 65개다. 이 수치는 timestamp 관계를
요약하며 원인, clock 보정, 실행 품질 또는 수익성을 주장하지 않는다.

재현 예시는 다음과 같다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.research_signal_anomaly_episodes \
  --archive-root <timestamp-forensics-archive> \
  --evidence-root <immutable-evidence-archive> \
  --output-dir <separate-output-directory>
```

출력 `summary.json`에는 `minutes`, `coincident_minutes`, `episodes`,
`pairwise_counts`, 총 관측·anomaly·동시 분·에피소드 수, 그리고 입력
`input_hashes`가 포함된다. 출력 디렉터리는 archive 밖이어야 하며, 기본 실행은
고정 입력 SHA가 다르면 중단한다.
