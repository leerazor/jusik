# PAPER 신호 timestamp forensic 분석

이 문서는 보존된 PAPER 관찰 아카이브의 `market_at`과 `received_at` 관계를
재현 가능한 방식으로 확인한 결과다. 분석기는 아카이브 안의 snapshot만
SQLite `mode=ro&immutable=1`로 열며, provenance에 기록된 원본 경로를 열지
않는다. WAL이 비어 있지 않거나 입력 SHA-256이 기준 기록과 다르면 중단한다.
분석 중 입력을 다시 해시해 시작 시점과 끝 시점의 바이트 동일성도 확인한다.

## 선택 규칙과 재현

선택일은 `2026-09-11`, 기준 시각은
`2026-09-12T00:51:19.514182Z`다. 가장 최근 `forward_sessions` 행을
`activated_at DESC`로 선택하고, SQL에서 UTC 범위
`[2026-09-10T00:00:00+00:00, 2026-09-13T00:00:00+00:00)`를 먼저 적용한다.
그 뒤 종목 registry의 timezone으로 시장일을 확인하고, 고정 달력의 정규장
범위 `[open, close)`에 들어오는 행만 latency 표본으로 사용한다. 따라서
open 시각은 포함하고 close 시각은 제외한다.

latency는 행마다 계산하며 같은 종목·분의 중복 행을 제거하지 않는다. coverage의
분 수는 기존 validator와 같은 종목·이유별 분 dedup 규칙을 사용한다. 이 차이로
latency 표본 수와 unique minute coverage 수가 달라질 수 있다.

재현 명령은 다음과 같다. 결과 디렉터리는 archive root 밖이어야 한다.

```bash
cd /path/to/jusik
PYTHONPATH=backend backend/.venv/bin/python -m jusik.research_signal_timestamp_forensics \
  --archive-root "$ARCHIVE_ROOT" \
  --output-dir "$PWD/.artifacts/signal-timestamp-replay"
```

분석기는 `summary.json`, anomaly 전체를 담은 `anomalies.csv`, 입력 파일의
before/after hash를 담은 `input-hashes.json`을 만든다. CSV는 validator의
50건 제한을 적용하지 않으며, observation ID·source·reason·quote JSON의
원본 market/received 문자열·DB timestamp 컬럼을 함께 보존한다.

## 기준 replay 결과

정규장 latency 표본은 6,164건이다. 중앙값은 `-130ms`, p95는 `668ms`, 최대는
`4,939ms`이고, `received_at - market_at < -2s`인 future anomaly는 249건,
`>15s`인 stale anomaly는 0건이다. 임계값은 모두 strict 비교이므로 정확히
`-2s`와 `+15s`인 행은 anomaly가 아니다.

| symbol | exchange | latency samples | future | stale | observed/expected minutes | missing | persisted rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 005930 | KSC | 380 | 60 | 0 | 380/390 | 10 | 398 |
| 000660 | KSC | 380 | 57 | 0 | 380/390 | 10 | 390 |
| 487230 | KSC | 380 | 30 | 0 | 380/390 | 10 | 383 |
| 487240 | KSC | 380 | 44 | 0 | 380/390 | 10 | 395 |
| 0173Y0 | KSC | 370 | 33 | 0 | 370/390 | 20 | 374 |
| 0190C0 | KSC | 374 | 25 | 0 | 374/390 | 16 | 381 |
| SOXL | PCX | 390 | 0 | 0 | 390/390 | 0 | 960 |
| NVDA | NMS | 390 | 0 | 0 | 390/390 | 0 | 960 |
| GOOGL | NMS | 390 | 0 | 0 | 390/390 | 0 | 955 |
| COHR | NYQ | 390 | 0 | 0 | 390/390 | 0 | 807 |
| TQQQ | NGM | 390 | 0 | 0 | 390/390 | 0 | 956 |
| MSFT | NMS | 390 | 0 | 0 | 390/390 | 0 | 894 |
| ARM | NMS | 390 | 0 | 0 | 390/390 | 0 | 772 |
| AMD | NMS | 390 | 0 | 0 | 390/390 | 0 | 944 |
| GEV | NYQ | 390 | 0 | 0 | 390/390 | 0 | 704 |
| VRT | NYQ | 390 | 0 | 0 | 390/390 | 0 | 862 |

이 표는 기준 `signal-validation.json`의 종목별 latency와 coverage 수치를 모두
재현해 비교한 것이다. 국내 종목의 future anomaly 합은
`60+57+30+44+33+25=249`이며, 미국 종목에는 없다. coverage의 persisted rows는
정규장 밖 행을 포함하므로 observed minutes와 직접 합산하지 않는다.

## 해석의 한계

`market_at`은 보존된 `ResearchQuote`에 들어 있는 시장 시각이고
`received_at`은 수신 호스트의 시각이다. 이 아카이브에는 원본 frame, 독립 NTP
clock-offset 측정, timestamp 생성·해석 과정이 없으므로 source timestamp 해석의
불확실성과 호스트 clock 오차를 분리할 수 없다. 이 차이는 관측된 timestamp
관계일 뿐 네트워크 원인이나 장애 원인을 확정하지 않는다. 분석기는 timestamp를
보정하지 않고 anomaly를 원인별로 분류하지도 않는다. 따라서 이 결과에서
인과관계, 실행 품질, 현재 연결 상태, 수익성을 주장할 수 없다.

정규장 밖 행과 누락 분은 coverage에 남겨지지만, 누락의 원인이 거래 공백인지
저장 정책인지 연결 상태인지는 이 자료만으로 구분하지 않는다. 이 아카이브에는
신호 판단과 fill이 없으므로 signal execution 품질도 평가하지 않는다.

이 frozen archive에서 선택된 행의 reason은 모두 `minute_sample`이고, symbol/minute
중복은 0건이다. UTC hour bucket은 normalized `market_at`의 시각을 기준으로 한다.
