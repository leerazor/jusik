# R1-04 회계 계약 첫 slice 중단

- 상태: 차단. 구현의 기술 완료나 전체 R1-04 완료를 주장하지 않습니다.
- 작업: `roadmap-r1-04-v1`; attempt `bf7be9ff5dd64096848f7599f0c8265f`.
- 기준: `5688c38b1f8c091db5e52d495df5262f5d1ed749`; 등록 커밋 `e84aa55`. 구현 main 통합 없음.
- 소유 worktree: `/home/kwl/projects/jusik-r1-actions-bf7b`, branch `feat/r1-actions-bf7b`. 미커밋 구현을 보존합니다.

## 범위와 변경

R0 완료를 확인한 뒤, 공통 history 모델·직렬화·snapshot hash를 바꾸지 않는 별도 연구용 split/dividend 입력 adapter와 순수 Decimal 회계 변환을 계획했습니다. Luna가 새 module, 테스트, fixture, 계약 문서와 개발 기록 초안을 작성했습니다. 이 구현과 계약 문서 초안은 main에 병합하지 않았습니다. collector·universe·사건 cutoff·전략·PAPER 계약은 변경하지 않았습니다. 실제 approximate source의 빈 actions·incomplete 상태도 그대로입니다.

## 차단 근거

- 작업 지시는 신규 회계 테스트와 기존 순수 회귀 두 개만 허용했습니다. Luna는 기존 `test_market_history_approximate.py`, `test_research_dividend_overlay.py` 파일 전체를 두 번 실행했습니다. 첫 실행 40개, 신규 회계 테스트를 포함한 마지막 실행 60개가 통과했습니다. 이 통과는 acceptance 통과가 아닙니다.
- 기존 approximate 테스트에는 합성 `stage="pilot"` 요청과 `run_approximate_market_research` 실행이 있습니다. 실제 자료 pilot 실행은 확인되지 않았지만, 이번 계획의 engine/pilot 0회 경계를 충족하지 못했습니다.
- 최초 신규 테스트 실행 후 입력 시나리오가 바뀌었습니다. 독립 Terra 감사에서 실행된 신규 fixture의 보수적 하한21개를 확인했습니다. 최종 목록19개는 시도 전체의 합집합이 아니며 상한20개를 초과했습니다. 결과는 외부 audit에 저장했습니다.
- code 역할의 첫 public receipt가 준비한 routing receipt와 일치하지 않아 사후 delivery 검증에 실패했습니다. 모델 불일치로 확대 해석하지 않습니다.
- 추가 계산·구현 병합·main 통합 검사를 중단했습니다. 범위·실행 이력과 receipt 불일치를 허용된 자동 복구 label로 바꾸지 않습니다.

## 검증과 제한

마지막 worker pytest60, Ruff check/format, configured strict mypy 통과 보고와 실제 pytest 결과를 보존했습니다. 그 이전 실패와 입력 변경도 보존했습니다. `tests_passed=false`, `review_passed=false`로 완료 응답을 제출합니다. main 통합 검사는 미실행입니다. 독립 검토는 추가 테스트 없이 실행 경계와 증거를 읽기 전용으로 확인합니다.

경제 평가는 `not-evaluated`입니다. 실제 행사 자료 연결, benchmark·미래 관찰 및 전체 R1-04 acceptance는 없습니다. 로드맵 체크박스는 미체크를 유지합니다. 성과 비교가 없어 웹 성과 catalog를 변경하지 않았습니다.

## 안전·운영 상태와 재개

실주문·PAPER/live 활성화·운영 DB/원장·서비스·설정·remote push·GPU 변경은 없습니다. 다른 격리 작업과 기존 handoff를 보존했습니다. 이번 worktree는 미병합·미커밋이므로 제거하지 않았습니다.

증거와 source snapshot은 `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-04-bf7be9ff/`에 있습니다. `observed-pytest-invocations.json`, `observed-pytest-results.json`, `code-routing-failure.json`, 독립 `review.md`, `evidence-manifest.json`, `HANDOFF.md`를 확인합니다. 다음 명시적 재시도는 같은 branch/worktree를 재사용하고, 변경 입력까지 포함한 전체 fixture 목록과 검사 명령을 실행 전에 고정해야 합니다. 이전 실패 기록을 삭제하거나 성공으로 재해석하지 않습니다.
