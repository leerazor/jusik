# R0-03 오프라인 deterministic replay

- 상태: 진행
- 기록 시각: 2026-09-15T00:00:00Z
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

## 문서·계약 영향

- 사용자 문서: `docs/market-research-replay.md`에 명령, 입력 검증, 출력과
  checkpoint 의미를 기록했습니다.
- 운영 문서: 해당 없음. 작업 등록부와 외부 audit 갱신은 감독 소유입니다.
- API·설정·데이터 계약: 기존 모델·서비스·전략은 변경하지 않았고 optional
  capture 인자만 추가했습니다.

## 검증

- frozen baseline checkpoint `2026-09-15T01:10:31Z` — replay exact comparison
  전체 통과, audit output은 저장소 밖에 보존했습니다.
- frozen future checkpoint `2026-10-15T01:10:31Z` — replay exact comparison
  전체 통과; 새 market observation으로 해석하지 않습니다.
- Ruff와 strict mypy — 구현 파일 통과.
- 전체 pytest와 신규 테스트 — 기록 시점에 추가 예정.

## 안전·운영 상태

- network, research DB, 서비스, PAPER·실주문, brokerage API, 원격 push를
  실행하지 않았습니다. frozen input은 읽기 전용으로 사용했습니다.
- 출력은 입력 디렉터리와 겹치지 않도록 검사하고 기존 output 파일을 덮어쓰지
  않습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay`;
  manifest: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json`
- 남은 작업·차단 조건: 신규 테스트 작성, 전체 관련 검사와 독립 review, main
  통합이 필요합니다.
- 다음 시작: `tests/test_market_research_replay.py`를 추가하고 실제 audit
  결과의 두 checkpoint 출력 hash와 오류 경로를 검증합니다.
