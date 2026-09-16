# 미국 사건 시점 보존

- 상태: 차단
- 기록 시각: 2026-09-16T03:00:00Z
- 작업 slug: `r1-us-event-timing`
- 기준/통합: `4385610` / 없음
- 범위: 미국 approximate collector의 Yahoo 사건 시점과 준비 dataset 계약. 기존 R1-01 membership hash, KR collector, 전략과 `snapshot.actions`는 보존합니다.

## 변경과 결정

- `ApproximateEvent`가 사건 종류, 발생 시각, 관측 시각, 공급원을 보존합니다. 관측 시각은 parser 호출 인자 또는 공급자 응답의 명시 필드만 사용합니다.
- source가 import된 dataset에도 동일한 사건 cutoff를 적용해 collector 경계를 우회한 행을 제거합니다. 동일 timing은 dedupe·canonical sort하며 서로 다른 관측 시각 또는 잘못된 시각은 보존 후 `insufficient`로 처리합니다.
- 발생·관측 시각이 모두 있는 사건은 두 시각 중 늦은 날짜부터 membership과 가격 행을 격리합니다. 사건이 요청 기간 뒤면 이전 prefix를 유지합니다.
- 시각이 없거나 날짜만 있는 사건은 dataset에 남기고 wrapper가 `insufficient`를 반환합니다. 사건을 `snapshot.actions`에 넣지 않아 전체 기간 unsupported-action 차단 의미를 바꾸지 않습니다.
- `approx-us-r1-event-timing-v1`과 새 policy hash를 사용하며 `approx-us-r1-membership-v1` 준비 artifact와 R1-01 hash를 읽을 수 있는 legacy 경로를 둡니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md`에 미국 사건 timing과 unknown 처리 규칙을 기록했습니다.
- 운영 문서: 해당 없음. 네트워크 수집·서비스·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: `ApproximateDataset.events`가 추가된 backward-compatible optional field입니다.

## 검증

- `backend/.venv/bin/python -m pytest -q tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 이전 focused 실행은 112개 통과였습니다. 부모의 `885a7bc` 검증은 130개 통과·1개 실패였고, delayed-event fixture의 후보 evidence가 비어 있던 문제를 이 후속 commit에서 보완했습니다. 현재 3개 fixture scenario를 추가하여 재검증 예상은 133개입니다. 신규 event fixture는 총 15개이며 모두 최대 300 sessions·8 symbols 범위 안의 결정적 입력입니다(난수 추출 없음, seed 0 계약).

부모 실행 focused pytest 파일: `tests/test_market_data_collector.py`, `tests/test_market_history_approximate.py`, `tests/test_market_research.py`.

| fixture group | count | max sessions | max symbols | seed |
| --- | ---: | ---: | ---: | ---: |
| parser and canonical timing | 4 | 1 | 1 | 0 |
| source unknown, future, conflict, and intraday bounds | 9 | 2 | 1 | 0 |
| collector future/delayed event and strategy prefix | 2 | 300 | 2 | 0 |
- broad `backend/.venv/bin/python -m pytest -q` — 2회 실행, 각 1123 passed·10 failed·1 skipped; wall 104.81s/101.04s, CPU 31.66s/29.82s. 실패 원인은 이 작업에서 분류하지 않았으며, 아래에 실패 파일과 경계를 그대로 기록합니다.
- broad 실행의 10개 실패는 `tests/test_development_runner_roadmap.py` 3개, `tests/test_market_research_replay.py` 1개, `tests/test_research_prospective_registration.py` 1개, `tests/test_research_signal_anomaly_episodes.py` 1개, `tests/test_research_signal_timestamp_forensics.py` 4개입니다. broad 실행에는 `tests/test_operations.py`의 paper fill/account 및 `tests/test_research_forward.py`의 `ForwardCoordinator`/`ForwardStore` 검사가 포함되어 내부 PAPER 시뮬레이션과 `tmp_path` 임시 DB mutation이 발생했습니다. 실제 broker 주문·외부 네트워크 호출은 확인되지 않았습니다. 작업 경계상 broad 실행은 부적절했으며 결과를 승격 근거로 사용하지 않습니다.
- 독립 venv의 `python -m ruff`는 Ruff 실행 binary 부재로 실행하지 못했고, 별도 설치 binary의 관련 파일 검사만 통과했습니다. 변경 source strict mypy는 통과했습니다. frozen replay 최종 검사는 commit 후 부모가 실행해야 합니다.

## 안전·운영 상태

- 실주문·live engine·운영 DB·원격 push는 실행하거나 변경하지 않았습니다. 범위를 벗어난 broad pytest에서 내부 PAPER 시뮬레이션과 `tmp_path` 임시 DB mutation이 발생했지만 운영 상태에는 연결되지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-02-c42012de`; manifest: `code-manifest.json`.
- 남은 작업·차단 조건: 실제 Yahoo 관측 시각의 역사적 근거가 없어 R1-02 전체 checklist는 차단 상태입니다. 독립 review와 전체 검증이 필요합니다.
- 다음 시작: 부모가 허용한 focused pytest 3개 파일, Ruff·mypy·frozen replay를 실행하고 독립 review를 진행합니다.
