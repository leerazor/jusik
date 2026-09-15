# R0-03 오프라인 deterministic replay

- 상태: 완료
- 기록 시각: 2026-09-15T04:23:32Z
- 작업 slug: `r0-deterministic-replay`
- 기준/통합: `dc7656d` / 없음
- 범위: frozen approximate baseline을 네트워크·DB 없이 검증하고 재실행하는
  CLI, checkpoint capture seam, 전용 테스트와 사용 문서를 추가했습니다.

## 변경과 결정

- `backend/jusik/market_research_replay.py`가 manifest가 가리키는 dataset·run·
  collector cache·completion marker의 파일 및 내부 hash/schema를 확인합니다.
- request, market, approximate grade, original readiness의 simulated 값, 고정
  policy/data/pool hash와 requirements lock이 기준선과 다르면 strategy 전에
  중단합니다.
- `market_history_approximate.py`의 `captured_at` 선택 인자는 snapshot capture
  metadata만 제어하며 `available_at`과 전략 수학은 보존합니다.
- 결과의 metrics·candidate evidence·trades·equity·limitations 및 계약 hash를
  baseline과 exact 비교하고, capture 의존적인 input hash는 별도로 기록합니다.
- catalogue에는 replay에 직접 영향을 주는 세 실행 모듈과 history source·model·
  calendar 코드·calendar JSON의 SHA-256 및 각 파일의 dirty flag를 기록합니다.
  manifest SHA는 읽은 바이트의 기록값이며, 외부 기대 digest가 없으면 독립
  identity 검증으로 해석하지 않습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research-replay.md`에 명령, 입력 검증, 출력과
  checkpoint 의미를 기록했습니다.
- 운영 문서: 해당 없음. 작업 등록부와 외부 audit 갱신은 감독 소유입니다.
- API·설정·데이터 계약: 기존 모델·서비스·전략은 변경하지 않았고 optional
  capture 인자만 추가했습니다.

## 검증

- `cd backend && .venv/bin/python -m pytest -q tests/test_market_research_replay.py
  tests/test_market_history_approximate.py tests/test_market_research.py` — 60
  passed (2 dependency deprecation warnings).
- `cd backend && .venv/bin/ruff format jusik/market_research_replay.py
  tests/test_market_research_replay.py jusik/market_history_approximate.py` —
  통과; `cd backend && .venv/bin/ruff check jusik/market_research_replay.py
  tests/test_market_research_replay.py jusik/market_history_approximate.py` —
  통과.
- `cd backend && .venv/bin/python -m mypy jusik/market_research_replay.py
  jusik/market_history_approximate.py tests/test_market_research_replay.py` —
  통과.
- 기준 checkpoint 실제 명령:
  ```text
  cd /home/kwl/projects/jusik-r0-deterministic-replay/backend && .venv/bin/python -m jusik.market_research_replay --manifest /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json --checkpoint-at 2026-09-15T01:10:31Z --output-dir /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay/final-baseline
  ```
  — `comparison.all=true`, replay SHA
  `ad17544ced4bca0530661e57e50ebe90503c5e61dd6e09e98669268d362c5eee`,
  catalogue SHA
  `1cb98b7ed8e30c1dd323b2d9ce7c1e02cb8e0428d208b3b53069cfafb5c152fa`, dirty
  `false`, executing Git SHA `bd7770db5d60978a63e58641909d7d38a292d3b6`.
- 미래 checkpoint 실제 명령:
  ```text
  cd /home/kwl/projects/jusik-r0-deterministic-replay/backend && .venv/bin/python -m jusik.market_research_replay --manifest /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json --checkpoint-at 2026-10-15T01:10:31Z --output-dir /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay/final-future
  ```
  — `comparison.all=true`, replay SHA
  `de97461b1fb9d021c7db037804c6db63b0a5ee019abfefa26d06668c130b7123`,
  catalogue SHA
  `57c75efcc446922385adf60bcdf635623d3837ebae5316ca4862c1dbef864caa`, dirty
  `false`, executing Git SHA `bd7770db5d60978a63e58641909d7d38a292d3b6`.

## 안전·운영 상태

- network, research DB, 서비스, PAPER·실주문, brokerage API, 원격 push를
  실행하지 않았습니다. frozen input은 읽기 전용으로 사용했습니다.
- 출력은 입력 디렉터리와 겹치지 않도록 검사하고 기존 output 파일을 덮어쓰지
  않습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay/final-baseline`와
  `final-future`;
  manifest: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json`
- 남은 작업·차단 조건: 독립 review 후 local `main` 통합과 통합 검증이
  필요합니다.
- 다음 시작: 부모 agent가 두 final catalogue를 보존하고 review 결과를 반영한
  뒤 local `main` 통합 검증을 실행합니다.

## 통합 검증

최종9cbc8da 독립 review 중요 지적 없음. main `b950266983970d32f014f809d51a802eadbf2572` 통합 후 pytest61개, Ruff format/check, strict mypy3개와 diff 검사를 통과했습니다. 통합 main의 실제 두 CLI 실행은 audit `r0-deterministic-replay/main-baseline`과 `main-future`에 보존했고 모두 comparison.all=true입니다. 전체 해시는 audit `integration-verification.json`에 연결했습니다. R0-01/02/03/04/05 완료이며 다음 R1/R2/R3는 별도 작업입니다.
