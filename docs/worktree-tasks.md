# 워크트리 작업 등록부

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

## experiment-guard

- 상태: 완료
- 목표와 완료 조건: 실험 엔진의 허용된 단일 변경과 대조군 전체 JSON 일치를 검증하는 읽기 전용 helper를 구현하고 독립 검토 및 main 통합 검증을 통과합니다.
- 담당 Luna: `/root/work_guard`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-experiment-guard`
- 작업 브랜치: `feat/experiment-guard`
- 기준 커밋 SHA: `e663641`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: `20260911T060908Z-rebalance-band/next-hypothesis.md`, 조사 및 계획 완료
- 수정 허용 범위: `backend/jusik/research_experiment_guard.py`, 해당 테스트, `docs/research-experiment-guard.md`
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 전용 워크트리 `.venv` 및 pytest 임시 경로 사용
- 검증 명령과 결과: focused pytest 9개, Ruff check/format, mypy 통과. 독립 review의 두 P2 수정 후 재검토 통과. main 병합 후 같은 검사 통과
- 보존 기준: 운영 엔진·원장·평가 계약·GPU 서비스 미변경. 시작 증거는 `20260911T132132Z-worktree-development/before.json`
- 결과 커밋 SHA: `41e3bbbac8f573a840d53d366cdef543af277792`
- 병합 직전 main SHA: `e663641`
- 통합 커밋 SHA: `8e421e55f2648455f6325b87738c48e12ceb0b79`
- 통합 보존 검사: 고정 파일 19개, 원장 9개 테이블, 계약 mtime, GPU PID·재시작 상태 일치
- 워크트리: 독립 환경과 검토 증거를 남기기 위해 이번 묶음 완료까지 보존. 작업 서버 없음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절

## unheld-entry-experiment

- 상태: 진행
- 담당 Luna: `/root/work_unheld`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-unheld-entry-experiment`
- 작업 브랜치: `feat/unheld-entry-experiment`
- 기준 커밋: `6c8eb32` 이후 이 배정 기록을 포함한 커밋
- 통합 대상: 로컬 `main`
- 목표와 완료 조건: 미보유 진입만 2%p 밴드 예외로 처리한 격리 엔진을 32회 비교하고 대조군 16개 전체 결과 일치, 경계 fixture 및 웹 보고서를 검증합니다.
- 입력과 선행 작업: experiment-guard의 첫 운영 검증과 통합 완료. 이전 rebalance-band audit의 고정 입력·대조군·사전 판정식 사용
- 수정 허용 범위: 새 실험 runner, 테스트, 별도 문서와 격리 산출물. 운영 엔진·기존 모델·PAPER 경로는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv` 및 워크트리 `validation/`, 공유 입력은 읽기 전용
- 검증: 행동·지표 fixture, 32회 비교, 대조군 16개 전체 일치, Ruff·mypy·독립 review·main 통합 검사, 웹 history 산출물 해시 확인
- 종료 조건: 결과를 성공 여부와 무관하게 공개하고 등록부·handoff와 운영 보존 증거를 갱신합니다.

## 첫 운영 검증

`experiment-guard`에서 완료했습니다. 운영 문서와 등록부를 기준 커밋에 포함했고, Luna가 전용 폴더·브랜치·가상환경에서 구현했습니다. 독립 검토, Astra의 로컬 main 병합, 통합 검사와 운영 상태 보존 검사를 통과했으며 handoff를 기록했습니다. 서버·DB·포트는 사용하지 않았습니다.

## 완료 작업

아직 완료된 작업이 없습니다. 완료 항목은 삭제하지 않고 이곳으로 옮겨 통합 커밋과 handoff 경로를 보존합니다.
