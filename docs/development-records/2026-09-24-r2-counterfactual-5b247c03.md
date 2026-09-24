# R2-06 오프라인 비교 재검증

- 상태: 기술 slice 검증 완료; 전체 R2-06 자료 acceptance 차단.
- 기록 시각: 2026-09-24T02:26:17Z.
- 작업: `roadmap-r2-06-v1`; attempt `5b247c03c8cb4d7d9ba651f9ea856204`.
- 기준/통합: 요청 최신 기준 `4c1e16204b7a39f9327e7d389a93b67f8c61eae7`의 자손인 local main에서 재검증. 비교 코드 변경과 병합 대상은 없음.

## 변경과 결정

- 기존 비교 모듈·CLI와 한국어 계약을 재사용했다. 준비 report 원본 SHA, 동일 계약, 한 시나리오당 단일 가정 변경, 비용·배당·FX의 별도 기준 차이, 비가산 출력 금지와 `unavailable` 보존을 읽기 전용으로 확인했다.
- 기존 소유 worktree는 이전 시도에서 증거 보존 후 정리되었고 이번 시도에 새 구현 작업이 없어 worktree를 만들지 않았다. runner child의 agent spawn 금지에 따라 구현에 참여하지 않은 현재 supervisor가 독립된 읽기 전용 검토를 수행했다.
- 실제 완전한 fills·corporate-action/배당·FX 근거와 동일 계약의 준비 결과, benchmark 및 미래 관찰이 없다. 경제 평가는 `not-evaluated`이고 R2-06 체크박스는 유지한다.

## 문서·계약 영향

- `docs/research/market-counterfactual-comparison.md`는 현재 동작과 일치하여 수정하지 않았다. 회계 엔진·API·설정·서비스와 사용자 동작은 변경하지 않았다.

## 검증

- `backend/.venv/bin/python --version`: Python 3.13.15.
- focused pytest: counterfactual·loss accounting 82개 통과.
- Ruff check/format과 configured strict mypy 통과.
- 현재 main의 읽기 전용 검토 통과. 결함 없음; 실제 경제적 성과는 검증하지 않았다.
- network/provider, historical engine/replay, GPU, PAPER/live, 주문, 운영 원장/DB, 서비스·설정, remote 변경 없음.

## 증거와 재개

- Audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r2-06-5b247c03/`; SHA manifest와 handoff를 보존한다.
- 재개 입력: 동일 기간·시장·통화·초기 자본·자료/정책 계약의 기준과 비용·배당·FX 단일 변경별 준비 report 원본 및 SHA, 완전한 fills·배당·FX 근거, benchmark와 미래 관찰. 그전에는 `unavailable/blocked`로 유지한다.
