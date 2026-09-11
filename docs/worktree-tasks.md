# 워크트리 작업 등록부

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

## experiment-guard

- 상태: 진행
- 목표와 완료 조건: 실험 엔진의 허용된 단일 변경과 대조군 전체 JSON 일치를 검증하는 읽기 전용 helper를 구현하고 독립 검토 및 main 통합 검증을 통과합니다.
- 담당 Luna: `/root/work_guard`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-experiment-guard`
- 작업 브랜치: `feat/experiment-guard`
- 기준 커밋 SHA: `2d255285b5b801a898f67718cf793bbf20fb0cf6` 이후 이 등록 항목을 포함한 커밋
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: `20260911T060908Z-rebalance-band/next-hypothesis.md`, 조사 및 계획 완료
- 수정 허용 범위: `backend/jusik/research_experiment_guard.py`, 해당 테스트, `docs/research-experiment-guard.md`
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 전용 워크트리 `.venv`, pytest 임시 경로 및 `validation/` 사용
- 검증 명령과 결과: pytest, Ruff check/format, mypy 및 독립 review 예정
- 보존 기준: 운영 엔진·원장·평가 계약·GPU 서비스 미변경. 시작 증거는 `20260911T132132Z-worktree-development/before.json`
- 결과 커밋 SHA·통합 검증·handoff: 완료 후 기록

## unheld-entry-experiment

- 상태: 준비
- 목표와 완료 조건: 미보유 진입만 2%p 밴드 예외로 처리한 격리 엔진을 32회 비교하고 대조군 16개 전체 결과 일치, 경계 fixture 및 웹 보고서를 검증합니다.
- 입력과 선행 작업: experiment-guard의 첫 운영 검증과 통합 완료 후 전용 워크트리를 배정합니다.
- 수정 허용 범위: 새 실험 runner, 테스트, 별도 문서와 격리 산출물. 운영 엔진·기존 모델·PAPER 경로는 변경하지 않습니다.

## 첫 운영 검증

아직 수행하지 않았습니다. 첫 실제 개발 작업에서 운영 절차의 첫 운영 검증 항목을 확인하고 결과를 기록합니다.

## 완료 작업

아직 완료된 작업이 없습니다. 완료 항목은 삭제하지 않고 이곳으로 옮겨 통합 커밋과 handoff 경로를 보존합니다.
