# PAPER 신호 근거 수집

Task: `paper-signal-evidence-v1` / Attempt: `722bb6f1d10a42318b502092d64dac39`

## 범위와 결론

이번 결과는 운영 `research-forward.db`에 이미 저장된 PAPER 실시간 시세 관찰을
바이트 단위로 보존한 뒤, 전용 복사본에 기존 `research_signal_validation`을 적용한
읽기 전용 근거다. 새 WebSocket·broker 요청·runtime endpoint·주문·엔진 재시작은
수행하지 않았다. 따라서 저장된 관찰이 존재한다는 사실은 확인하지만 현재 소켓
연결성, 실시간 전달 품질, 체결 품질 또는 미래 수익성을 입증하지 않는다.

원본 DB와 WAL은 SQLite로 열지 않고 읽었으며, 복사 전·후·검증 후의 원본 바이트가
같았다. 전용 복사본의 `integrity_check`는 `ok`였다. 이번 검증의
`operational_evidence`는 `operational_unproven`, `current_feed`는 `null`이다.

## 관측 시각과 선택일

검증 결과 생성 시각은 `2026-09-12T00:51:19.514182Z`이고, provenance 기록의
수집 종료 시각은 `2026-09-12T00:51:19.736327+00:00`이다. 최신 저장 관찰은
시장 시각 `2026-09-11T23:59:34+00:00`, 수신 시각
`2026-09-11T23:59:33.597939+00:00`이다. provenance의 validator 기준 시각에서
최신 수신 age는 `3105.916243`초(약 51분 45.916초)였다.

고정 달력으로 선택한 완료 거래일은 `2026-09-11`이다. 전체 저장 관찰은
21,937건이며 출처별로 `KIS H0STCNT0` 4,209건, `KIS HDFSCNT0` 17,728건이다.
별도로 보존된 durable feed 사건은 159건이며, 범위는
`2026-09-10T01:09:33.578375Z`부터 `2026-09-12T00:00:19.075329Z`까지다.

## 선택일 coverage

선택일 정규장 기준은 종목별 390분이다. `persisted_rows`에는 정규장 밖에 저장된
행도 포함되므로 정규장 관찰 분과 직접 합산하지 않는다.

| 종목 | 거래소 | 정규장 관찰/기대(분) | 누락(분) | 저장 행 | 정규장 밖 행 |
| --- | --- | ---: | ---: | ---: | ---: |
| 005930 | KSC | 380/390 | 10 | 398 | 18 |
| 000660 | KSC | 380/390 | 10 | 390 | 10 |
| 487230 | KSC | 380/390 | 10 | 383 | 3 |
| 487240 | KSC | 380/390 | 10 | 395 | 15 |
| 0173Y0 | KSC | 370/390 | 20 | 374 | 4 |
| 0190C0 | KSC | 374/390 | 16 | 381 | 7 |
| SOXL | PCX | 390/390 | 0 | 960 | 570 |
| NVDA | NMS | 390/390 | 0 | 960 | 570 |
| GOOGL | NMS | 390/390 | 0 | 955 | 565 |
| COHR | NYQ | 390/390 | 0 | 807 | 417 |
| TQQQ | NGM | 390/390 | 0 | 956 | 566 |
| MSFT | NMS | 390/390 | 0 | 894 | 504 |
| ARM | NMS | 390/390 | 0 | 772 | 382 |
| AMD | NMS | 390/390 | 0 | 944 | 554 |
| GEV | NYQ | 390/390 | 0 | 704 | 314 |
| VRT | NYQ | 390/390 | 0 | 862 | 472 |

국내 6종목에서 누락은 각각 10, 10, 10, 10, 20, 16분이며 모두
`2026-09-11T06:20:00Z`~`06:30:00Z` 구간을 포함한다. `0173Y0`과 `0190C0`에는
이 구간 외의 추가 1분 단위 공백도 있다. 미관측 분만으로 거래 공백·저장 정책·연결
상태 중 원인을 확정하지 않는다.

## 지연과 anomaly

정규장 분 표본 6,164건의 집계 지연은 중앙값 `-130ms`, p95 `668ms`, 최대
`4,939ms`였다. 시장 시각이 수신 시각보다 2초 넘게 미래인 anomaly는 249건이며,
validator가 보존한 anomaly 항목은 최대 50건으로 잘려 있다(`truncated=true`).
15초 초과 표본은 0건이다. 미래 시각 anomaly 249건은 모두 국내 KSC 표본에서
발견됐고, 종목별 건수는 `005930` 60, `000660` 57, `487230` 30,
`487240` 44, `0173Y0` 33, `0190C0` 25건이다. 원인은 이번 수집에서 단정하지
않는다.

## 판단·체결과 운영 한계

선택일 validator 결과에서 `decisions=[]`, `executions=[]`이며, provenance의
전체 세션 테이블도 `forward_decisions=0`, `forward_fills=0`,
`forward_observations=21937`이다. 그러므로 이번 근거에는 신호 판단이나 fill의
quote provenance가 없다. 0건은 판단·체결이 성공했다는 뜻도, 실패했다는 뜻도
아니다.

`operational_unproven`은 captured fill 근거가 없다는 뜻이고,
`current_feed=null`은 현재 feed 연결 상태를 이 검증에서 관측하지 않았다는 뜻이다.
저장 관찰은 과거 수집 구간의 증거이며 현재 live stream 연결, 주문 가능성, 실행 품질,
전략 수익성을 보장하지 않는다. source 바이트 동일성도 서비스가 계속
동작한 상태에서의 이번 캡처 구간만 보장하며 서비스 중단을 의미하지 않는다.

## provenance와 영구 경로

영구 audit 경로는 다음과 같다.

`/home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39/`

그 안의 `signal-validation.json`과 `provenance.json`이 위 수치의 원본 결과다.
안정화한 비공개 DB 복사본과 WAL은 각각 다음 경로에 있다.

- DB: `private/forward-snapshot.db`
- WAL: `private/forward-snapshot.db-wal`
- DB SHA-256: `7c901a51b7bcf2b2f192760a4b29cdcbf7a4b4ef177db69ca9c5f9146b168c15`
- WAL SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 원본 경로: `/home/kwl/.local/share/jusik/research-forward.db`

재현에 필요한 validator·quote model·달력과 전체 의존 소스는 audit의
`source/jusik/`에, `pyproject.toml`과 `requirements.lock`은 audit의 `source/`에
보존했다. 이번에 사용한 코드·달력 SHA-256은 각각 다음과 같다.

| 파일 | SHA-256 |
| --- | --- |
| `source/jusik/research_signal_validation.py` | `3e92f379f715caab2dbd3efd4fa7efc6f00865fe8259ce3706afc9ad04897a1b` |
| `source/jusik/research_quote_models.py` | `b082553dadcc87f6a4df473ebeb746071a0d9ed90bce2fc07e25972ed4bf5b61` |
| `source/jusik/data/market_sessions_2023_2026.json` | `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8` |

## 재생 지침

보존된 snapshot만 대상으로, provenance의 validator 기준 시각과 선택일을 그대로
사용해 재생한다. 아래 코드는 원본 DB에 접근하지 않으며 결과 JSON이 보존된 결과와
일치하는지 확인한다. audit에는 환경 버전과 의존성 선언만 보존되어 있으므로,
아래 예시는 기존 Python 3.13 backend venv를 사용한다.

```bash
AUDIT=/home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39
cd "$AUDIT"
PYTHONPATH="$AUDIT/source" /home/kwl/projects/jusik/backend/.venv/bin/python - <<'PY'
import json
from datetime import date, datetime
from pathlib import Path

from jusik.research_signal_validation import validate_signal_store

audit = Path("/home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39")
result = validate_signal_store(
    audit / "private/forward-snapshot.db",
    local_date=date.fromisoformat("2026-09-11"),
    now=datetime.fromisoformat("2026-09-12T00:51:19.514182+00:00"),
    current_feed=None,
)
expected = json.loads((audit / "signal-validation.json").read_text())
assert result.model_dump(mode="json") == expected
print("replay matches signal-validation.json")
PY
```

이 지침의 `now`는 결과의 정확한 `generated_at`이며, provenance의 수집 종료 시각
`2026-09-12T00:51:19.736327+00:00`과 혼동하지 않는다. 재생은 과거 snapshot의
동일한 분석을 확인하는 절차이며 새 데이터 수집, 현재 연결 확인, 주문 또는 수익성
평가가 아니다.

## 검사

수집 환경에서 `tests/test_research_validation.py`와 `tests/test_kis_stream.py`는
29개 통과했고 기존 deprecation warning 2건이 있었다. 관련 Ruff check/format은
4개 파일에 대해 통과했으며 validator·quote model strict mypy도 2개 소스 파일에서
통과했다. 상세 로그는 audit의 `tests-before.log`, `lint-before.log`,
`types-before.log`에 보존했다. 이 문서는 PAPER 운영 코드나 DB를 변경하지 않는다.
