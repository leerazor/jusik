# R2-06 counterfactual 재검증 중단

- 상태: 차단. 기술 수정은 미병합이며 전체 R2-06은 미완료입니다.
- 기록 시각: 2026-09-23T13:20:16Z
- 작업: `roadmap-r2-06-v1`; attempt `2817a7d9b9274b7ea6fa3810a98ed32e`
- 기준: main `450bf982e52663c0cad641fd43e7442c4d463ea2`. 요청 원본 `d0d029996ea993216036385962c9153968ea61fe`는 조상입니다. 이전 attempt의 주요 입력 SHA 6개가 현재 파일과 일치했습니다.

## 변경과 결정

- 단일 Luna worktree `/home/kwl/projects/jusik-r2-counterfactual-2817a7d9`의 `ba0a10e93e37303af4741024b9fe8461e1ab56ef`은 저장 JSON의 소수 숫자 literal 및 비표준 `NaN`/`Infinity`를 거절하고 회귀 테스트와 한국어 계약을 보완했습니다.
- 독립 review 1차에서 저장 JSON의 float 정밀도 손실과 비표준 숫자 허용을 찾았습니다. 수정 뒤 2차 review에서 공개 `ComparisonEnvelope.from_mapping`이 float 초기 자본을 반올림해 수용하고 고정 가정의 `NaN`을 결과에 기록할 수 있음을 재현했습니다. 같은 숫자 입력 불변식이 두 review에서 실패해 사용자 중단 조건을 적용했습니다. review 미통과로 구현 커밋을 main에 병합하지 않았고 local-main 통합 검사는 실행하지 않았습니다.
- 기존 loss accounting 엔진과 availability 의미는 수정하지 않았습니다. 실제 준비 결과가 없어 경제 평가는 `not-evaluated`이며 R2-06 체크박스는 유지했습니다.

## 문서·계약 영향

- 사용자 계약 수정은 작업 브랜치의 `docs/research/market-counterfactual-comparison.md`에만 있습니다. 검토 미통과로 main 계약은 그대로입니다.
- API, 서비스, 설정, 운영 데이터 계약 변경은 없습니다. 새 성과 비교가 없어 웹 공개도 해당하지 않습니다.

## 검증

- 소유 venv Python 3.13.15 확인 후 focused pytest 72개 통과, Ruff check/format 및 configured strict mypy 통과. 저장 로그는 아래 audit에 있습니다.
- 독립 review는 미통과. 공개 in-memory 입력의 정밀도·비유한 값 차단을 검증하지 못했습니다.
- local-main 통합 검사는 미실행: 구현 브랜치를 병합하지 않았습니다.

## 안전·운영 상태와 재개

- provider/network 수집, historical engine/replay, GPU, PAPER/live, 주문, 운영 원장/DB, 서비스·설정, remote 변경은 없습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-r2-06-2817a7d9/`; `manifest.json`에 파일 SHA-256이 있습니다. `review.md`에 두 review의 핵심 근거, `HANDOFF.md`에 재개 지점이 있습니다.
- worktree와 branch는 미병합 상태로 보존합니다. 다음 bounded attempt에서 먼저 공개 mapping 입력의 float/NaN 경로를 닫고 focused 검사와 독립 review를 새로 수행합니다. 완전한 fills·초기 포지션·corporate-action/배당·FX 근거를 갖춘 동일 계약의 준비 결과와 benchmark·미래 관찰은 전체 R2-06 경제 acceptance에 여전히 필요합니다.
