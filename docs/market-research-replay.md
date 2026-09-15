# 시장 연구 deterministic replay

R0-03 replay는 frozen baseline manifest가 가리키는 prepared dataset, 완료된
run, collector cache manifest와 completion marker를 읽어 같은 approximate 연구
계산을 다시 실행합니다. 네트워크, 환경 자격증명, 연구 DB와 brokerage API를
사용하지 않습니다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_research_replay \
  --manifest /absolute/path/to/baseline-manifest.json \
  --checkpoint-at 2026-09-15T01:10:31Z \
  --output-dir /absolute/path/to/replay
```

`--checkpoint-at`은 aware UTC ISO-8601 시각이어야 합니다. 이 값은 snapshot의
`captured_at`만 정합니다. dataset 행의 `available_at`, 거래소 달력, source,
요청, 전략 정책과 결과 계산은 변경하지 않습니다. 따라서 미래 checkpoint를
사용해도 새로운 시장 관측을 추가한 것으로 해석하지 않습니다.

실행 전 manifest 자체와 네 artifact의 SHA-256, dataset schema·행 수·가용 기간,
cache의 모든 raw entry, completion marker, request·market·grade·simulation,
policy/data/pool contract hash와 requirements lock을 확인합니다. 확인에 실패하면
strategy를 호출하지 않고 종료합니다. 출력 디렉터리가 입력 경로와 겹치거나
`replay.json` 또는 `catalogue.json`이 이미 있으면 기존 파일을 보존한 채
거부합니다.

성공하면 출력 디렉터리에 두 파일을 원자적으로 생성합니다.

- `replay.json`: checkpoint, replay `MarketResearchResult`, 배열별 exact 비교
  결과.
- `catalogue.json`: manifest·입력 artifact hash, frozen baseline code SHA와 현재
  실행 Git SHA/source hash, Python·platform·lock 환경, snapshot input hash,
  output hash와 비교 결과.

`metrics`, `candidate_evidence`, `trades`, `equity`, limitations, status와
`policy_hash`, `data_contract_hash`, `pool_contract_hash`를 baseline과 exact
비교합니다. `input_hash`는 capture 시각을 포함하므로 catalogue에 기록하지만
capture가 다른 실행과의 동등성 조건으로 요구하지 않습니다.
