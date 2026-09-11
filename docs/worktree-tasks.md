# 워크트리 작업 등록부

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

### development-runner

- 상태: 진행
- 목표와 완료 조건: 지속 개발 실행기를 설치하고 영속 큐, 중복 실행 방지, 중지/재개, 시간·실행 횟수 한도, 웹 이력 표시와 실제 Codex 실행을 검증합니다.
- 담당 Luna: `/root/work_attribution` (새 작업으로 재배정)
- 워크트리 절대 경로: `/home/kwl/projects/jusik-development-runner`
- 작업 브랜치: `feat/development-runner`
- 기준 커밋: `cb075f2b09d2dbbfa55c5c58ba2dfca6dcb72313`
- 통합 대상: 로컬 `main`
- 입력과 선행 작업: explore·plan 완료. Codex CLI 로그인과 Astra 비대화형 shell 실행 검증 완료
- 수정 허용 범위: 신규 실행기·상태 저장·테스트·systemd 템플릿·운영 문서. 기존 거래 엔진·PAPER·GPU 변경 금지
- 포트·테스트 DB·출력 경로: 새 포트 없음. 작업별 `.venv`와 `validation/`, 테스트 DB는 임시 경로
- 검증: 큐 전이·잠금·중단 복구·시간 한도·결과 검증·공개 문구, 독립 review, main 통합 검사, 서비스 설치·웹 확인
- 보존 증거: `20260911T211748Z-autodev-install/before.json`
- 완료 절차: 코드 통합·검증 후 사용자 systemd에 설치, 기존 자료 보존 확인, handoff 갱신


## 완료 작업

### entry-attribution

- 상태: 완료
- 목표와 완료 조건: 고정된 미보유 진입 실험 32개의 종목별 회계 손익 및 월별 포트폴리오 손익·거래·비용을 독립 재계산하고 16쌍의 차이를 웹에 공개합니다. 재계산 잔차는 0.000001원 이하여야 합니다.
- 담당 Luna: `/root/work_attribution`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-entry-attribution`
- 작업 브랜치: `feat/entry-attribution`
- 기준 커밋: `ff607a7`
- 통합 대상: 로컬 `main`
- 입력과 선행 작업: 이전 32회 `unheld-entry-real32`의 고정 results/preregistration SHA 및 개별 artifact SHA. explore와 plan 완료
- 수정 허용 범위: 새 `research_entry_attribution.py`, 해당 테스트, `docs/research-entry-attribution.md`만 수정합니다. 전략·엔진·PAPER·API·UI는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv`와 `validation/` 사용, 기존 입력은 읽기 전용
- 검증 방법: 종목·월 합계와 기존 지표의 일치, split 현금정산·비용·UTC 경계·변조·누락·중복·불완전 입력 테스트, 실제 32개/16쌍 분석, 결정성 비교, Ruff·mypy·독립 review·main 통합 검증
- 보존 증거: `20260911T185925Z-entry-attribution/before.json`
- 결과 커밋: `603d50f61182b939c1d23d1083b135748c285d26`
- 병합 직전 main: `ff607a7`; 코드 통합 `e893698`, 최종 코드 상태 `d59a095a1d5d54421868865f0cb09b4321c880ef`
- 이력 보존: 작업자가 최초 리뷰 커밋 `6040b37`을 amend한 사실을 확인했습니다. 감독은 최종 검토 트리를 유지하면서 최초 스냅샷도 추가 병합의 조상으로 보존했고 이후 수정은 새 커밋으로 남기도록 재지시했습니다. 최종 트리는 검토한 `603d50f`와 동일합니다.
- 검증 결과: 신규 12개·관련 41개 테스트, 독립 리뷰 통과. main 전체 pytest 510개(기존 경고 2개), Ruff check/format 112개 파일, mypy 72개 소스 통과. UI 미변경으로 빌드는 미실행
- 실제 결과: 32개 artifact / 16쌍 / 종목 222행 / 월 126행. 별도 계산과 손익 값 1,044개가 정확히 일치하고 최대 회계 잔차는 `2.4375E-31 KRW`. 전용 두 실행 및 main 재실행의 산출물 4개가 동일
- 해석: 체결 금액에는 슬리피지가 반영돼 있으므로 수수료와 FX 비용만 현금흐름에서 차감합니다. 내재 슬리피지는 별도 표시합니다. 회계 귀속을 추가 매매의 인과적 이익이나 MDD 원인으로 해석하지 않습니다.
- 웹: `/research/history`의 `entry-attribution-20260912`. 판단·상세 보고서·종목/월 전체 CSV·검증 보고서 5개, API/웹 다운로드 10개 SHA와 화면 제목 확인. 이전 51개 이력과 78개 artifact 보존
- 보존: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 프로세스 상태 일치. 운영 전략과 PAPER 계약 미변경
- 산출물·정리: 워크트리 `validation/real-run-13`, `real-run-14` 및 영구 audit `20260911T185925Z-entry-attribution/verified-analysis`, `main-analysis`. 독립 환경과 재현 자료를 위해 워크트리를 보존하며 미커밋 소스·작업 서버는 없음
- handoff: 기준 저장소 `HANDOFF.md` 최신 기여 분석 절 갱신. 이번 범위에서 원격 push·PR은 수행하지 않음

## 이전 완료 작업

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
- 워크트리: 후속 검토에서 독립 가상환경과 구현 이력을 재현하기 위해 보존. 미커밋 소스와 작업 서버 없음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절

## unheld-entry-experiment

- 상태: 완료
- 담당 Luna: `/root/work_unheld`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-unheld-entry-experiment`
- 작업 브랜치: `feat/unheld-entry-experiment`
- 기준 커밋: `ad06daa`
- 통합 대상: 로컬 `main`
- 목표와 완료 조건: 미보유 진입만 2%p 밴드 예외로 처리한 격리 엔진을 32회 비교하고 대조군 16개 전체 결과 일치, 경계 fixture 및 웹 보고서를 검증합니다.
- 입력과 선행 작업: experiment-guard의 첫 운영 검증과 통합 완료. 이전 rebalance-band audit의 고정 입력·대조군·사전 판정식 사용
- 수정 허용 범위: 새 실험 runner, 테스트, 별도 문서와 격리 산출물. 운영 엔진·기존 모델·PAPER 경로는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv` 및 워크트리 `validation/`, 공유 입력은 읽기 전용
- 검증: 행동·지표 fixture, 32회 비교, 대조군 16개 전체 일치, Ruff·mypy·독립 review·main 통합 검사, 웹 history 산출물 해시 확인
- 종료 조건: 결과를 성공 여부와 무관하게 공개하고 등록부·handoff와 운영 보존 증거를 갱신합니다.
- 결과 커밋: `eb9c0eed84b3657eb1a79af62b5d134457139205`
- 병합 직전 main: `ad06daa`
- 통합 커밋: `78045f84027243390728ef8c796a31f480d43e2b`
- 검증 결과: 신규 10개·기존 포트폴리오 19개 테스트 통과, 독립 리뷰 수정 및 재검토 통과. main 전체 pytest 498개(기존 경고 2개), Ruff check/format 110개 파일, mypy 71개 소스 통과. UI 미변경으로 프런트엔드 빌드는 미실행
- 실험 결과: 32/32 완료, 대조군 16개 전체 JSON 일치. 비용 1배 연속 수익률 16.3268% / 27.8639%, MDD 7.3744% / 7.2249%(대조군 / 변형군). 체결 171 / 308건이며 첫 fold 악화도 공개. 두 비용 조건의 사전 관심 기준 충족은 후향 연구 결과이고 PAPER 승격이 아님
- 웹: `/research/history`의 `unheld-entry-20260911`. 요약·전체 수치·16쌍 비교·검증 보고서 4개를 게시하고 API/웹 다운로드 8개 해시 및 화면 제목 확인. 첫 작업 이력과 모든 이전 이력 보존
- 보존 검증: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 서비스 상태 일치. 통합 코드와 실험 runner/helper hash 일치
- 산출물: 워크트리 `validation/real32` 및 영구 audit `20260911T132132Z-worktree-development/unheld-entry-real32`. 최초 `/tmp/jusik-unheld-real32`도 삭제하지 않음
- 워크트리: 독립 가상환경과 실험 재현 자료를 위해 보존. 미커밋 소스와 작업 서버 없음. 원격 push·PR은 이번 범위에서 수행하지 않음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절 갱신

## 첫 운영 검증

`experiment-guard`에서 완료했습니다. 운영 문서와 등록부를 기준 커밋에 포함했고, Luna가 전용 폴더·브랜치·가상환경에서 구현했습니다. 독립 검토, Astra의 로컬 main 병합, 통합 검사와 운영 상태 보존 검사를 통과했으며 handoff를 기록했습니다. 서버·DB·포트는 사용하지 않았습니다.
