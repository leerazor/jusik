# 워크트리 작업 등록부

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

없습니다. 자동 개발 큐와 실행 중인 작업은 전용 runner DB와 웹 연구 이력에서 확인합니다.

## 완료 작업

### entry-amount-distribution-v1

- 상태: 완료
- 목표와 완료 조건: 기존 32개 결과의 진입 금액 분포 분석을 재사용해 저장소에 통합하고 재현·독립 리뷰·게시·handoff를 완료합니다. 거래 제약은 구현하지 않습니다.
- 담당 Luna: entry_amount (gpt-5.6-luna), 단일 구현 소유자
- 워크트리: /home/kwl/projects/jusik-entry-amount-distribution-v1; 브랜치 feat/entry-amount-distribution-v1
- 기준: a725004; 통합 대상 로컬 main
- 입력과 계획: b73bef5d 시도의 완료된 explore/plan, analysis/analyze.py·test_analyze.py와 독립 계산을 재사용합니다. 새 조사는 현재 코드 호환성에 한정합니다. 고정 원본 32개·manifest를 읽기 전용으로 검증합니다.
- 수정 허용 범위: backend/jusik/research_entry_amount_distribution.py, 대응 테스트, docs/research/entry-amount-distribution-v1.md. 등록부·게시·handoff는 Astra 소유입니다.
- 환경: 워크트리 전용 .venv 및 validation, 서버·DB 없음. 영구 audit entry-amount-distribution-v1-5ed7695c
- 검증: focused pytest, Ruff, strict mypy, 고정 입력 재현 및 기존 독립 수치 대조, 독립 review, main 재실행
- 중단 조건: 입력 해시·회계·수량 불일치. 임계값 선택·추가 전략 실험은 범위 밖입니다.
- 결과 커밋: 6719c36fe61f09dc134f86d90fe31d6c7c81014c. 병합 직전 main a725004, 통합 f8143f9eb103510c9835e0593264d8e42d557c64
- 검토: 독립 review 통과. 재현 명령 줄 연결 수정 후 재검토 완료
- 통합 검증: 관련 pytest 28개(기존 경고 2개), backend 전체 Ruff check/format, strict mypy 75개 소스 통과. 32개 결과·820 BUY, 독립 1,728개 수치 및 기존 기계 산출물 3개 바이트 일치
- 보존: 원본 36개 JSON·기존 backend 모듈 SHA 동일. 실주문·push·PAPER 엔진/DB·GPU 변경 없음
- 웹: entry-amount-distribution-20260912, 5개 문서·API/웹 다운로드 10개 해시 및 제목 확인. 기존 이력 보존. mount root 교체 실패는 파일 단위 게시로 복구
- 환경·결과·handoff를 영구 audit entry-amount-distribution-v1-5ed7695c에 보존하고 archive-manifest.json 해시 대조 후 worktree remove 완료. 브랜치 보존
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/entry-amount-distribution-v1-5ed7695c/handoff.md 및 루트 HANDOFF.md. 통합 검사 실패 없음. UI 변경 없음으로 frontend build 생략


### 2026-09-12 병합 워크트리 정리

- 사용자 지시에 따라 독립 하위 작업은 최대 4명으로 병렬 진행하고, main 병합·통합 검증 후 완료 워크트리를 제거하는 원칙을 운영 문서에 반영했습니다.
- `development-runner`, `entry-attribution`, `experiment-guard`, `unheld-entry-experiment` 4개가 main의 조상이며 미커밋 변경과 사용 중인 프로세스가 없음을 확인했습니다.
- validation 결과 132개 파일을 SHA-256으로 대조해 `20260911T221657Z-worktree-cleanup/`에 보관했습니다. 각 환경의 패키지 버전도 보관했습니다.
- `git worktree remove`로 4개 폴더와 내부 가상환경·캐시를 제거했습니다. 강제 옵션은 사용하지 않았으며 커밋과 브랜치 이력은 유지했습니다.
- 아래 완료 항목의 워크트리 보존 기록은 당시 상태입니다. 현재 재현 자료의 위치는 위 cleanup audit과 기존 연구 audit입니다.
- 설정 갱신 중 자동 실행기를 일시 중지했으며, 진행 중이던 진입 금액 분석은 이전 시도 기록과 함께 재시도하도록 복구합니다. PAPER와 GPU 서비스는 변경하지 않습니다.

### development-runner

- 상태: 완료
- 목표: 영속 연구 큐를 Codex supervisor에 전달하는 자동 실행기를 설치하고 반복 실행·중단·웹 이력을 검증합니다.
- 담당 Luna: `/root/work_attribution` (새 작업으로 재배정)
- 워크트리: `/home/kwl/projects/jusik-development-runner`, `feat/development-runner`, 기준 `cb075f2b09d2dbbfa55c5c58ba2dfca6dcb72313`
- 결과 커밋: `406a897`, 수정 `312761f`, 최종 `fd2df78`. append-only 이력
- 병합 직전 main: `2c9a7ef`; 로컬 통합: `a49b30a`
- 범위: 신규 runner/store/테스트, systemd service/timer, 운영 문서와 README 안내. 감독이 AGENTS 운영 안내를 추가했습니다.
- 검증: 신규 13개 테스트, 독립 리뷰 통과. main 전체 pytest 523개(기존 경고 2개), Ruff 116개 파일, strict mypy 74개 소스 통과. UI 변경이 없어 frontend build는 미실행
- 실제 검증: Codex Astra 호출·Luna 위임·완료 schema 호환성, 가짜 작업의 systemd 단독 2회 및 타이머 자동 2회, 시작/완료 이력 전송, SIGTERM interrupted 저장과 자식 종료, 분리된 자식의 cgroup timeout 종료를 확인했습니다.
- 설정: 작업당 90분, UTC 하루 8회 시작, 종료 뒤 약 2분 간격. 금액 상한은 아니며 실패/중단 작업은 명시적 retry 전까지 보존합니다.
- 운영 설치: 사용자 `jusik-development-runner.service`와 `.timer`, 별도 상태 DB·비공개 로그, 기존 연구 history journal 연동. 사용자 linger 활성화. 초기 연구 5개 큐와 선행 조건을 등록했습니다.
- 리뷰 수정: 1초 이상 실행의 stdin 재전송 오류, 살아 있는 이전 process group 확인, SIGTERM/SIGINT 중단과 빠른 자식 종료 race를 수정하고 회귀 검증했습니다.
- 완료의 의미: runner는 commit·artifact hash를 확인하며 tests/review 결과는 agent 보고로 구분합니다. 기존 PAPER·GPU·실주문 경로는 변경하지 않습니다. 작업별 자세한 연구 결과는 후속 supervisor가 웹에 게시합니다.
- 증거: `20260911T211748Z-autodev-install/`의 main-pytest.log, timer-fixture-result.json, signal-fixture-result.json, cgroup-smoke-result.json, preservation-latest.json
- 보존·정리: 고정 19개 파일·9개 원장 테이블·GPU 상태 보존 확인. 재현용 워크트리와 독립 `.venv`는 보존하며 임시 검증 unit은 제거했습니다. 운영 unit만 유지합니다.
- handoff: 기준 저장소 `HANDOFF.md` 최신 절 갱신. 원격 push·PR은 이번 범위에서 수행하지 않았습니다.

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

## runner-git-access

- 상태: 완료
- 목표와 완료 조건: 자동 실행기의 Git 메타데이터 쓰기를 명시적으로 허용하고 실제 Codex의 워크트리 생성·커밋·main 병합·정리 및 보호 경로 차단을 검증한 뒤 기존 작업을 재개합니다.
- 담당 Luna: 별도 Codex CLI `gpt-5.6-luna` (내장 agent의 세션 한도로 대체)
- 워크트리 절대 경로: `/home/kwl/projects/jusik-runner-git-access`
- 작업 브랜치: `fix/runner-git-access`
- 기준 커밋 SHA: `8268a2d`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: 조사·계획 완료. 실제 Codex named permissions profile 쓰기 시험 통과
- 수정 허용 범위: development_runner.py, 관련 테스트, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv와 validation. 운영 runner는 pause 상태. 영구 audit `20260911T234908Z-runner-git-access/`
- 검증 명령과 결과: runner 22개, main 전체 pytest 532개(기존 경고 2개), Ruff check/format 115개 파일, strict mypy 74개 소스 통과. 실제 Codex exec 및 통합 helper 설정의 Git lifecycle·보호 경로·artifact 쓰기 검증 통과
- 검토 결과와 남은 문제: 독립 검토의 artifact 경로·기존 권한·테스트 격리 지적 수정 후 재검토 통과. 사용자 설정·quota·기존 산출물·PAPER·GPU 보존. 전용 환경의 선택 PyTorch 미설치로 최초 전체 검사 12개 실패, 최종 main 전체 검사 통과
- 결과 커밋 SHA: `9e0fcb1`, `21a9856`, `f6ba0aa`
- 병합 직전 main SHA: `e054390`
- 통합 커밋 SHA와 정리 여부: `58f5443a8f43428a717b707bb80cbb667db44706`. 검증 로그·환경 버전 보존 및 해시 확인 후 워크트리 제거 완료. 브랜치 보존
- 웹: `/research/history`의 `runner-git-access-20260912`. 기존 seed 52개·artifact 83개 보존, API/웹 다운로드 SHA와 제목 확인
- handoff 저장 경로와 갱신 여부: 기준 저장소 HANDOFF.md 복구 절과 영구 audit activation.json에서 재개 상태 확인


## future-observation-protocol-v1-63c4

- 상태: 완료
- 목표와 완료 조건: 후향 자료와 분리된 미래 관측 설계를 문서화하고 미확보 자료를 구분합니다. 독립 검토, 로컬 main 통합, 검사와 영구 handoff를 완료합니다.
- 담당 Luna: /root/protocol_luna (gpt-5.6-luna)
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-63c4
- 작업 브랜치: docs/future-observation-63c4
- 기준 커밋 SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 완료, 이전 시도 protocol-draft.md 및 현재 prospective/boundary 코드
- 수정 허용 범위: docs/research-future-observation-protocol.md, docs/research.md의 링크
- 포트·테스트 DB·출력 경로: 서버·운영 DB 사용 없음. 검사는 격리 임시 경로 사용
- 검증 명령과 결과: main 문서 링크·계약 일치·git diff --check·변경 범위·보존 해시 통과. prospective/boundary pytest 40개 통과(기존 경고 2개), Ruff check/format 8개 파일, strict mypy 4개 소스 통과. 문서 변경으로 frontend build 비적용
- 결과 커밋 SHA: d80abd9c8d8bdc0bfb1733891967f5675d18432b
- 검토 결과와 남은 문제: 독립 review 초기 지적 수정 후 최종 통과. 미래 관측·운영 등록·성과 검증은 완료되지 않았으며 설계 범위 밖
- 병합 직전 main SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 커밋 SHA와 정리 여부: 69894b0e89b227ae24aa1a15fb0b30c234d7f514. 영구 audit에 증거 16개·SHA-256·handoff 보존 및 해시 확인 후 clean 워크트리 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-v1-63c4e3f2380b4e149d60d17db90459c7/handoff.md 저장 완료
- 웹: runner completion/outbox를 통한 상태 기록 대상. 직접 게시·history 변경은 하지 않았습니다. 기존 미추적 HANDOFF.md를 보존했습니다.


## paper-signal-evidence-v1-722b

- 상태: 완료
- 목표와 완료 조건: 저장된 실시간 PAPER 시세 근거를 읽기 전용 수집하고 출처·제한을 문서화합니다. 독립 검토, main 통합, 검사, 영구 근거와 handoff 보존을 완료합니다.
- 담당 Luna: paper_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-paper-signal-722b
- 작업 브랜치: docs/paper-signal-722b
- 기준 커밋 SHA: 0676b70 (작업 등록 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 순차 완료. 이전 시도 collector와 기존 research_signal_validation 재사용
- 수정 허용 범위: docs/research/paper-signal-evidence-v1.md (Luna); 등록부·영구 audit 수집·검증·handoff (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음. 테스트는 임시 DB, 수집은 audit/private 복사본만 사용
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39
- 검증 계획: snapshot integrity와 재분석 일치, validation/kis_stream pytest, Ruff check/format, strict mypy, 문서 독립 review와 main 통합 재검사
- 중단 조건: 원본 수집 중 변경·무결성 실패·해시 불일치. 운영 DB·engine·broker·주문·GPU·remote 변경 금지

- 결과 커밋 SHA: 4f0542f (Luna)
- 병합 직전 main SHA: 0676b70
- 통합 커밋 SHA: e9d7b5da40218a36a84fd6e7552cfc88f7dc7c1a
- 검토 결과: 독립 snapshot 재분석·별도 집계 일치. 문서 경로·환경 설명 수정 후 독립 검토 통과
- 검증 결과: 통합 전후 pytest 29개 통과(기존 경고 2개), Ruff check/format 4파일, strict mypy 2소스 통과. 문서 hash 일치·diff check·baseline 보존 확인. frontend build 해당 없음
- 관측 결과: 저장 관찰 21,937건, 판단·체결 0건. 선택일 2026-09-11의 6,240분 중 6,164분 관측, 미래 시각 이상 249건. current_feed=null, operational_unproven 유지
- 정리: 필요한 근거 99파일과 SHA-256·handoff를 영구 audit에 먼저 보존·검증했다. clean worktree 제거 완료, 브랜치 보존. 최종 보존 목록은 manifest.json 참조
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39/handoff.md
- 웹: runner completion/outbox의 상태 기록 대상이며 직접 게시하지 않았다. 기존 미추적 HANDOFF.md 보존


## portfolio-stress-e16e

- 상태: 차단 (오프라인 검토·문서 통합 완료, 미래 성과 미확보)
- 목표와 완료 조건: 고정 오프라인 스트레스 재계산과 문서 검토·main 통합·검사·영구 handoff. 미래 성과는 자료 부족으로 차단합니다.
- 담당 Luna: stress_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-stress-e16e
- 작업 브랜치: docs/portfolio-stress-e16e
- 기준 커밋 SHA: 29c5327768e298a284171cce8ec933e1a274ed29 (등록 준비 전 main; 실제 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 조사와 bounded plan 완료. 기존 고정 baseline과 robustness CLI
- 수정 허용 범위: docs/research/portfolio-stress-robustness-v1.md (Luna); 등록부·audit·검사 (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음, 테스트는 임시 DB. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0
- 검증 계획: 고정 SHA, 7 folds/147회 평가, 시간 분리, 관련 pytest·Ruff·strict mypy·독립 review
- 중단 조건: 고정 입력 hash 불일치 또는 계산 실패. 엔진·PAPER·주문·remote·GPU 변경 금지

- 결과 커밋 SHA: c52b08d65aa4fda62793b23da3f64f4300c2419e
- 병합 직전 main SHA: a7e18e71d5cd305d0c73e93d978e6c6772dd3834
- 통합 커밋 SHA: a63ef98b8fd46d09a3a5f3e13dc29db0a3fff54c
- 검토 결과: 독립 검토 통과. source/code/spec/산출물 해시, 9개 요약 수치, fold 시간 분리, 이전 결과 일치 검증. 재현 경로와 미래 평가 표현 수정
- 검증 결과: 통합 전후 pytest 31개 통과(기존 경고 2개), Ruff check/format 및 strict mypy 통과. diff check·문서 hash·기존 HANDOFF와 엔진 보존 확인. frontend build 비적용
- 연구 결과: 7/7 folds, 147회 평가, 774 union dates. 생성 시각 외 이전 결과 일치. 2026-09-12 기준 미래 평가 기간이 아직 시작되지 않아 성과 검증 차단
- 정리: 필요한 근거·SHA-256·handoff 26파일을 영구 audit에 보존하고 검증한 후 clean merged worktree 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0/handoff.md
- 웹: runner completion/outbox 상태 기록 대상. 직접 게시·PAPER DB 변경 없음. 기존 미추적 HANDOFF.md 보존


## paper-signal-timestamp-forensics-a77e

- 상태: 완료
- 목표와 완료 조건: 동결 snapshot의 6,164개 정규장 표본과 미래 시각 이상 249건을 재현하는 오프라인 CLI, 전체 anomaly CSV, 그룹별 요약, 경계 테스트와 한국어 문서를 구현합니다. 독립 검토, local main 통합 검사, 웹 보고서와 영구 근거 보존 후 종료합니다.
- 담당 Luna: timestamp_luna (gpt-5.6-luna), 신규 모듈·테스트·문서 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-timestamp-a77e
- 작업 브랜치: feat/signal-timestamp-a77e
- 기준 커밋 SHA: fa127374e6e3ee351fedb514ffb0db1769615437 (등록 전 main; 실제 worktree 기준은 이 등록의 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 독립 재계산 완료, plan 순차 검토. paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39의 snapshot/provenance/validation만 읽기 전용 입력으로 사용합니다.
- 수정 허용 범위: backend/jusik/research_signal_timestamp_forensics.py, backend/tests/test_research_signal_timestamp_forensics.py, docs/research/paper-signal-timestamp-forensics-v1.md (Luna); 등록부·audit·웹 seed·handoff (Astra)
- 포트·테스트 DB·출력 경로: 신규 서버 없음. worktree 내부 .venv와 .artifacts, pytest tmp 경로를 격리합니다. 운영 DB에 연결하지 않습니다.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6
- 검증 명령과 결과: 새 pytest 및 research_validation 회귀, Ruff check/format, strict mypy, 두 번 frozen replay의 바이트 일치와 입력 SHA 보존, 독립 review, main 통합 후 동일 검사 예정
- 중단 조건: 입력 hash 불일치 또는 구현 범위 밖 변경 필요. 미래 데이터는 본 오프라인 도구 완료의 조건이 아닙니다. PAPER·collector·order·parser·clockmonitor·GPU·runner·quota·remote를 변경하지 않습니다.
- 결과 커밋 SHA: 92527281cdadd5101478987d233db5b5931ec909, ab56a15d80bdc02772a13460c2d1c0588ac99e26
- 병합 직전 main SHA: a6610f047b0c460a61cef0cd7cee9794dd4013f6
- 통합 커밋 SHA: 3f1a0f59edc9643210647e14fc6090918a1bfded
- 검토 결과: Terra 독립 검토 통과. 정확한 -2s-1µs fixture와 URI 인코딩 지적을 회귀 테스트와 함께 수정했습니다.
- 통합 검증 결과: pytest 20개(기존 Starlette/AnyIO 경고 2개), Ruff check/format, 프로젝트 설정 strict mypy 2파일, git diff 검사 통과. 두 main 재생 3출력 바이트 일치, 249개 ID/시각/정확한 지연 및 전 종목 latency/coverage와 독립 집계 일치. frontend build 비적용.
- 결과: 6,164개 정규장 저장 분 표본, future 249건, stale 0건, median -130ms/p95 668ms/max 4939ms. 원 snapshot 및 기존 소스·HANDOFF 해시를 유지했습니다. 원인은 확정하지 않았습니다.
- 웹: /research/history에 한국어 보고서·checks 게시 완료. API/웹 4개 첨부 다운로드 SHA와 페이지 제목 확인. 기존 seed의 54개 이력·89개 첨부를 보존했습니다.
- 정리: evidence·SHA-256·환경·handoff 등 105개 파일을 영구 audit에 보존·검증한 뒤 생성물을 정리하고 git worktree remove로 병합 worktree 제거 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음. 사전 감독 mypy의 잘못된 cwd를 backend로 바꾸어 프로젝트 Pydantic plugin 및 strict 설정 적용 후 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6/handoff.md. 기존 루트 미추적 HANDOFF.md는 그대로 보존했습니다.
- 후속 후보: 독립 근거의 68개 다중 종목 이상 분을 이용한 오프라인 동시 발생/연속 episode 분석 1개. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.


## small-entry-draft-a55b

- 상태: 완료
- 목표와 완료 조건: 신규 소액 진입 사전등록 초안 명세·검증기·테스트를 만들고 독립 검토, local main 통합 검사, 한국어 웹 게시와 영구 근거 보존을 완료합니다. 금융 승인이나 정책 실행은 포함하지 않습니다.
- 담당 Luna: draft_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자. 초기 작업자는 파일 수정 전에 중단했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-a55b
- 작업 브랜치: feat/small-entry-draft-a55b
- 기준 커밋 SHA: 8882bd8287759edc047adc296da129cded8950dc (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 완료, 순차 bounded plan. 완료 entry amount 분석과 original unheld-band는 역사 맥락으로만 사용합니다. 과거 blocked 작업은 보존합니다.
- 수정 허용 범위: backend/jusik/research_small_entry_preregistration.py, backend/tests/test_research_small_entry_preregistration.py, docs/research/small-entry-preregistration-draft-v1.md. Astra는 등록부·audit·공개 history·handoff를 담당합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp 경로 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542
- 검증 방법: threshold/time/period/hash 경계, canonical roundtrip와 별도 identity, populated draft 불변성, pytest·Ruff·strict mypy·독립 review·main 재검사.
- 중단 조건: 세 파일 도구 완료. 임계값 탐색·정책 실행·PAPER 코드/config/DB·collector/order/GPU·runner/quota·remote 변경 금지. 미래 자료 부재는 도구 완료를 막지 않습니다.

- 결과 커밋 SHA: 0f8e1c674bc1535ee80caf500973b143123551e8, 92f3648481a8822a603eedcc82a1213c00d33452
- 병합 직전 main SHA: 03cdafd4b476c55430093d3dad2a6f453e286d80
- 통합 커밋 SHA: 4bd8a85e2d3c482fddaca47a85fe8d64c51d65ad
- 검토 결과: 독립 검토 통과. 추가 금액 계산 helper의 Decimal context 반올림 지적을 helper 제거로 해결하고 위조 상태·중첩 위험 한도의 출력 거부 회귀를 추가했습니다.
- 통합 검증 결과: 신규19개 및 기존 금액 분석6개 pytest 합계25개, Ruff check/format, 설정된 strict mypy 신규 소스·테스트2파일, diff 검사 통과. 기본·합성 완전 입력 반복 canonical 출력/roundtrip/낮은 Decimal context 바이트와 SHA 일치.
- 검사 제한: 전체 backend mypy의 torch 타입 정보 누락·기존 테스트 모듈 중복2오류를 변경 전 main에서도 재현했습니다. frontend build 비적용. 엔진·실험 정책 실행 테스트는 범위에서 제외했습니다.
- 결과: 기본4개 결정은 null, 모든 입력이 있어도 draft 및 활성화 금지. canonical draft SHA 71691f864ccc0e61e351b52298027e6df4e8c864ab9c15f16ae0887bbfe35dbb. PAPER10% 계약과 기존 코드/config/HANDOFF·역사 입력 SHA 보존.
- 웹: /research/history 한국어 보고서·검사 요약 게시 완료. API/웹 제목과4개 첨부 다운로드 SHA 및 기존 seed 이력 보존 확인.
- 정리: 근거62파일·환경·SHA·handoff를 영구 audit에 먼저 보존·검증한 뒤 작업 생성물과 병합 worktree를 git worktree remove로 제거했습니다. 브랜치는 보존했습니다. 최종 manifest.json에 정리 후 추가 기록까지 포함합니다.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542/handoff.md. 기존 root HANDOFF.md 보존.
- 후속 후보: 초안의 선언 SHA와 실제 보관 출처를 검증하는 신규 오프라인 provenance bundle verifier1개. exact scope/input/tests/stop은 영구 followup.json 참조. 미래 자료·금융 승인 불필요.


## future-observation-replay-0bb3

- 상태: 완료
- 목표와 완료 조건: 합성 fixture 전용 순수 관측 분류기와 오프라인 CLI를 구현하고 독립 기대값·pytest·검토·main 통합·웹 보고 및 영구 증거 보존을 완료합니다.
- 담당 Luna: replay_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-replay-0bb3
- 작업 브랜치: feat/future-observation-replay-0bb3
- 기준 커밋 SHA: de52818e3ec249ef1bd9e42e80ad2304befa1eb1 (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 미래 관측 초안, readiness/receipt seam 읽기 전용 조사 완료. 순차 bounded plan과 독립 합성 기대값을 사용합니다.
- 수정 허용 범위: backend/jusik/research_future_observation_replay.py, backend/tests/test_research_future_observation_replay.py, docs/research/future-observation-protocol-replay-v1.md. Astra는 등록부·audit·공개 history·handoff 담당.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp와 cache 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b
- 검증 방법: UTC 반열린 구간, 최초 receipt 불변, 중복·충돌·late, not_due/missing, clock/truncation, 미정 우선순위 보존, 고정 synthetic 불변성. pytest·Ruff·strict mypy·독립 review와 main 재검사.
- 중단 조건: 결정론적 합성 replay 도구까지. 미래 데이터 부재는 blocker가 아닙니다. PAPER 코드/config/contracts/DB·collector·order·GPU·runner/quota·remote 변경 금지.

- 구현 커밋: af61404, 23a425b, 8ad7113, 0bcf2cc, 420d04a, 2f5fecc. 독립 검토에서 미래 receipt 소급·시계 오류 건수·CLI alias 회귀를 발견해 동일 Luna가 수정했습니다.
- 감독 독립 검증: 10 receipt/8 identity fixture, 수신 전후 conflict/provenance/clock 3개 비교 통과. 최종 독립 검토와 main 통합 검사 후 완료 처리합니다.

- 최종 구현 커밋: 2f5fecc (수정 이력 포함). 독립 최종 검토 PASS, 중요 미해결 지적 없음.
- 병합 직전 main SHA: 6f320bd5e40bef99bb7da03e8996e590239744d6
- 통합 커밋 SHA: d83d47f2d289368f1719aff9ed516143cb35b091
- 통합 검증 결과: pytest 49개(신규20, readiness/receipt29), Ruff check/format, 신규 두 파일 strict mypy, diff 통과. 기존 deprecation 경고2개. frontend build 비적용, 전체 backend 타입 검사 미실행.
- 독립 결과: 10 receipt/8 identity 기대값, 두 CLI 출력 바이트, 미래 conflict/provenance/clock의 수신 전후3쌍 비교 통과. 모든 결과 synthetic, registered/accepted_nav/evaluation_inputs_complete=false.
- 웹: /research/history 한국어 보고서·checks 게시 완료. API·웹 제목과4개 첨부 다운로드 SHA, 기존 공개 seed 보존 확인.
- 보존: 기존 tracked 파일은 등록부 외 모두 동일하며 기존 미추적 HANDOFF.md 보존. 비ASCII 경로2개는 원래 기준 커밋 bytes와 추가 비교. 운영 DB·PAPER·collector·order·GPU·runner/quota·remote 변경 없음.
- 정리: 증거·SHA·환경·handoff82파일을 영구 audit에 보관·검증한 뒤 생성물을 제거하고 git worktree remove로 병합 worktree 정리 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 코드 통합 검사 실패 없음. 감독 보존 검사에서 Git 경로 인용으로 비ASCII2파일이 새 파일로 오인되어 -z 경로 읽기와 기준 blob 비교로 검사 도구를 수정하고 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b/handoff.md
- 후속 후보: 합성 revision-link 구조 감사1개. 프로토콜의 이전 revision·effective 시각 연결 규칙과 현재 replay의 충돌 보존 범위를 근거로 합니다. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.

## runner-daily-limit

- 상태: 완료
- 목표와 완료 조건: 기존 실행 이력을 보존하며 일일 설정 상한을 24회까지 지원하고 설치 설정을 24회로 조정해 대기 연구를 재개합니다.
- 담당 Luna: 별도 Codex CLI gpt-5.6-luna
- 워크트리 절대 경로: /home/kwl/projects/jusik-runner-daily-limit
- 작업 브랜치: fix/runner-daily-limit
- 기준 커밋 SHA: 8d9333f
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: UTC 실행 8회/설정8로 quota 대기 확인; 후속3개 queued, timer 정상
- 수정 허용 범위: development_runner.py, 해당 tests, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv/임시DB, 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T061307Z-runner-daily-limit
- 검증 명령과 결과: worker/main focused pytest 28개, Ruff check/format, strict mypy 통과. 독립 review P1/P2 없음
- 보존·종료: store/실행이력/90분제한/cooldown/PAPER/GPU 유지, main 검증 후 archive·worktree 정리·handoff·웹 게시
- 결과 커밋: ffdd7e3fb76a4120f5e05a988f0f2083089b7309
- 통합 커밋: ebc42b29c32734e86bbb71cdc0389171ea5166b1
- 정리: 로그·환경·해시 archive 후 worktree 제거, 브랜치 보존
- 설치: daily_launches 8에서24 변경, 나머지 설정과 과거 launch 행 전체 보존
- 재개·웹·handoff: HANDOFF.md 최신 절 및 audit activation.json 참조

## signal-anomaly-episodes-21ce

- 상태: 준비
- 목표와 완료 조건: 동결 신호의 분별 동시 이상/episodes utility, 테스트, 한국어 보고서; 249 IDs, 68분, 최대5종목 일치
- 담당 Luna: gpt-5.6-luna 단일 구현 작업자
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-anomaly-episodes-21ce
- 작업 브랜치: feat/signal-anomaly-episodes-21ce
- 기준 커밋 SHA: 등록 커밋 직후 HEAD (registration.json에 기록)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정된 evidence/timestamp archive manifest 전체 검증; explore와 plan 완료
- 수정 허용 범위: backend/jusik/research_signal_anomaly_episodes.py, backend/tests/test_research_signal_anomaly_episodes.py, docs/research/paper-signal-coincident-anomaly-episodes-v1.md
- 포트·테스트 DB·출력 경로: 전용 venv/pytest tmp; durable audit /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-coincident-anomaly-episodes-v1-21ce4592e34a4ee78332f2dbff95f994
- 검증 명령과 결과: 예정 pytest, Ruff check/format, strict mypy, immutable frozen replay, 독립 review, 통합 후 반복검증
- 결과 커밋 SHA: 대기
- 검토 결과와 남은 문제: 대기
- 병합 직전 main SHA: 대기
- 통합 커밋 SHA와 정리 여부: 대기
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: 위 durable audit/handoff.md 예정
