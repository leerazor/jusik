# 미국 사건 시점 보존

- 상태: 기술 slice 통합·검증 완료; 실제 관측 시각 증거가 없어 R1-02 전체 체크는 보류
- 기록 시각: 2026-09-16T03:00:00Z
- 작업 slug: `r1-us-event-timing`
- 기준/통합: `4385610` / `bcf34c5b16889cc209f249173cc935cce39681a6`
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

- `backend/.venv/bin/python -m pytest -q tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 이전 focused 실행은 112개 통과였습니다. 부모의 `bca348b` 검증은 130개 통과·1개 실패였고, delayed-event fixture의 후보 evidence가 비어 있던 문제를 후속 commit에서 보완했습니다. 현재 3개 fixture scenario를 추가하여 재검증 예상은 133개입니다. 신규 event fixture는 총 15개이며 모두 최대 300 sessions·8 symbols 범위 안의 결정적 입력입니다(난수 추출 없음, seed 0 계약).

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

## 중단 이후 복구 검증 (2026-09-16T03:20:35.446235+00:00)

기존 clean worktree의 최종 구현 `03b837f`를 재사용했습니다. 새 독립 Terra 정적 검토는 P1/P2 없음이며, 감독이 지정한 collector/history/replay 세 파일만 검사했습니다. 병합 전과 main 통합 후 pytest134, 관련 Ruff, configured mypy2 source가 통과했습니다. 동결 R0 replay는 모든 비교 항목이 일치했습니다. broad suite와 PAPER/forward 검사는 재실행하지 않았으며 이전 경계 일탈 기록은 보존합니다.

증거는 `/home/kwl/.local/share/jusik/portfolio-audit/20260916-roadmap-recovery/r102-premerge`와 `r102-integrated`에 있으며, 이전 자동 시도의 codex_exit 원인은 종료 코드가 저장되지 않아 확정하지 않았습니다. 기술 slice가 통합됐어도 실제 Yahoo 관측 시각의 과거 근거를 만들거나 R1-02 checkbox를 체크하지 않습니다. 다음 작업은 해당 자료 한계를 유지한 후속 데이터 품질 개발입니다.

## 재시도 확인 (2026-09-19, 0fec3e1577aa4ed789ce66b02d87e0aa)

`roadmap-r1-02-v1` 재시도는 자료 부족으로 차단했습니다. 현재 main
`816e180cc2dd22d0ae4f9fe67d1dd0f66d27a1e6`에는 기존 통합 `bcf34c5`와 후속
synthetic 불변성 통합 `91cb1bbe`가 모두 포함됩니다. 이전 소유 워크트리와 브랜치는
이미 정리되어 있어 중복 생성하지 않았습니다. 현재 코드·fixture·계약을 읽기 전용으로
대조했으며 추가 기술 결함은 확인하지 못했습니다. 실제 historical observed-at receipt와
거래중단 coverage의 원문 근거가 제공되지 않아 R1-02 checkbox는 미체크로 유지합니다.
배당·분할 회계는 이 재시도 범위 밖이며 별도 차단 요건으로 추가하지 않습니다.

R0 동결 입력 4개의 SHA-256을 다시 대조해 모두 일치함을 확인했습니다. 현재 mandate의
bytes SHA-256은 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`입니다.
pytest·Ruff·mypy·동결 replay 실행과 독립 구현 검토는 이번 시도에서 하지 않았습니다.
이전 통과 결과를 새 시도의 통과로 재사용하지 않습니다. 신규 fixture와 검증 실행은 0개이며,
과거 테스트 횟수 제한이나 경계 위반을 현재 차단 원인으로 삼지 않았습니다.

Luna 읽기 전용 조사는 반환됐지만 model-only routing의 pre만 통과했고 post는
`FAIL verification unavailable or failed`를 반환했습니다. 이를 검증된 routing 또는
독립 review 통과로 표시하지 않습니다. 완료 gate는 우회하지 않습니다.

코드·금융 자료·운영 DB·서비스·설정·PAPER/live·원격에는 변경이 없습니다. 경제 성과나
strict PIT 승격을 주장하지 않으며 웹 성과 공개도 하지 않습니다. audit와 handoff는
`/home/kwl/.local/share/jusik/portfolio-audit/20260919-r1-02-0fec3e15`에 보존합니다.
재개에는 출처와 사건 발생·관측 시각을 확인할 수 있는 원문 및 거래중단 coverage가
필요합니다. 이후에도 새 focused 검사와 독립 검토를 통과하기 전 완료로 표시하지 않습니다.
