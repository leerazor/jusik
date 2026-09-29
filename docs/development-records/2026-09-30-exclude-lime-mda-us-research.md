# 신규 미국 연구에서 LIME·MDA 제외

- 상태: 기술 완료; 투자 성과 미평가.
- 기록 시각: 2026-09-29 23:30 UTC.
- 작업 slug: `exclude-lime-mda-us-research`.
- 기준/통합: `0c4d8fb7f1183a88a92fd3d7b4ef3c1226bbd8a5` / 로컬 `main` `2394294e4246537a26986cd05066f4cf3eca1457`.
- 범위: 사용자가 확정한 대로 앞으로 생성하는 모든 미국 연구 표본에서 `LIME`·`MDA`를 제외합니다. 과거 동결 결과·원본 응답·cache·replay는 보존합니다.

## 변경과 결정

- 미국 collector는 연간 listing checkpoint의 seed·빈자리 보충 전에 두 심볼을 제외합니다. 새 결과는 `approx-us-r1-event-timing-v2` 정규화와 별도 pool 계약·진단의 정책 제외 목록을 기록합니다. 새 US 출력 경로가 이미 있으면 provider 호출 전 거부하고, 별도 완료 marker 및 원자적 신규 파일 생성으로 기존 v1 증거를 덮어쓰지 않습니다.
- 새 연구 서비스와 공개 전략 경로는 prepared·strict·근사 입력의 실행 membership·bar·action에서 두 심볼을 제외합니다. 원본 artifact는 남기고, 기존 준비 파일에는 대체 종목을 소급 추가하지 않으며 축소 표본·제외 이유를 결과에 표시합니다. 새 미국 정책·자료 계약 hash를 결속하고 이전 pilot을 새 final의 근거로 거부합니다.
- 동결 manifest replay만 내부 legacy 경로를 사용합니다. 공개 전략 호출에서 과거 정책 우회 인자를 제거하고 직접 호출의 이전 자료 hash 혼합을 거부합니다. 기존 원본의 366개 결손은 소급 정상화하지 않으며 R1-05/PIT/경제 평가 상태는 올리지 않습니다.

## 문서·계약 영향

- 사용자 계약: `docs/market-research.md`, `docs/investment-development-roadmap.md`에 신규 표본과 축소 표본의 차이, 기존 R1-05 대기를 명시했습니다.
- 정책: `docs/research-mandate.json`에 신규 미국 연구 정책 projection을 추가하고 `docs/research-mandate.md`, `docs/research.md`, `docs/market-research-mandate.sha256`을 동기화했습니다. immutable legacy execution projection SHA `f097fde7874063314e21f8be884b19d2e8cea3e1272c47e5991300c546548a7d`는 유지됩니다. 현재 전체 mandate SHA는 `2c0b41ef4246c8f9bc0c99f1b4d544364e2350371bf5fa3f4cee2d9ce3e62749`입니다.
- runner 설정·DB schema·전략 기준·PAPER/live 설정은 바꾸지 않았습니다.

## 검증

- 전용 워크트리 구현 focused pytest 289 passed. 독립 review가 공개 우회, 직접 자료 hash, 출력 덮어쓰기 세 결함을 지적해 원 구현자가 보정했습니다. 최종 독립 review PASS. 마지막 사전 출력 차단의 회귀 3개도 별도 PASS.
- 통합 `main`: `backend/.venv/bin/python -m pytest -q --basetemp=.venv/pytest-exclude-us-main`와 관련 6개 테스트 파일 — **290 passed**, 비차단성 deprecation warning 2개.
- 통합 `main`: 변경 Python Ruff check, 선택 10개 파일 Ruff format check, 7개 소스 strict mypy, `validate_mandate(Path(".."))`, `git diff 0c4d8fb..HEAD --check` 모두 통과.
- collector와 해당 테스트의 전체 Ruff format check는 기준 커밋부터 실패하는 기존 서식 차이가 있어 파일 전체를 재포맷하지 않았습니다. 전체 mypy는 선택 의존성 `pyarrow`·`torch` 미설치로 작업 범위 밖 오류가 있으며 변경된 7개 소스 strict mypy는 통과했습니다. 프런트엔드 변경이 없어 빌드는 실행하지 않았습니다.

## 안전·운영 상태

- 공개 공급자 호출·새 시세 수집·실제 주문·PAPER/live 승격·추가 결제·원격 push는 수행하지 않았습니다. 원본 cache·동결 결과는 수정하지 않았습니다.
- 개발 동안 roadmap runner는 pause, service inactive로 유지했습니다. 문서 통합 뒤 tracked clean을 확인하고 기존 설정으로 재개합니다.
- 사용자 소유 미추적 루트 `HANDOFF.md`는 그대로 보존합니다.

## 증거와 재개

- 코드 커밋: `b5be880`, `c3b6d60`, review 보정 `b0cf4aa`, 최종 사전 차단 `2394294`.
- 다음 시작: runner 상태·mandate gate와 새 attempt를 확인합니다. 새 선정 규칙으로 자료를 다시 준비할 경우 새 출력 경로와 원본 cache를 사용하고, 두 심볼을 제외한 실제 coverage·비용 포함 결과를 별도 검증합니다. 기존 R1-05 대기 attempt를 새 정책만으로 완료 처리하지 않습니다.
