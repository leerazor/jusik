# 구조 안내

이 문서는 새 개발자가 읽는 최소 구조 지도입니다. 상세 동작은 링크한 기능·운영 문서와 코드가 기준입니다.

## 실행 단위와 경계

| 단위 | 역할 | 주요 진입점 | 바꾸기 전 읽을 문서 |
| --- | --- | --- | --- |
| 포트폴리오 백엔드 | KIS·키움의 읽기 전용 계좌 조회와 투자자 후보·논거 API | `backend/jusik/main.py`, `backend/jusik/investor_api.py` | `README.md`, `docs/investor-workflow.md` |
| 연구 백엔드 | 모의 연구, 시장 자료 준비 상태, PAPER 관찰과 연구 이력 API | `backend/jusik/research_app.py`, `backend/jusik/market_research_api.py` | `docs/research.md`, `docs/market-research.md`, `docs/research-mandate.md` |
| 프런트엔드 | Next.js 화면과 두 백엔드의 서버 측 호출 | `frontend/app/`, `frontend/lib/investor.ts`, `frontend/lib/research.ts` | `frontend/AGENTS.md`, 관련 기능 문서 |
| 개발 실행기 | 제한된 연구·공학 작업의 큐·증거·상태 관리, 빈 큐에서 독립 검토를 거친 공학 과제 발굴 | `backend/jusik/development_runner.py`, `backend/jusik/development_runner_discovery.py`, `deploy/systemd/` | `docs/development-runner.md`, `docs/worktree-workflow.md` |
| 자율 연구소 제어 계층 | 작업 대기 분리·공학 작업 분류·offline 전략 전이 보호 | `backend/jusik/development_runner.py`, `backend/jusik/strategy_lifecycle.py` | `docs/autonomous-trading-lab.md`의 현재 구현/후속 구현 구분 |

`start.sh`는 포트폴리오 백엔드, 연구 백엔드, 프런트엔드를 함께 준비합니다. 프런트엔드는 투자자 요청에 `backendUrl()`을, 연구 요청에 `researchBackendUrl()`을 사용합니다. 두 API 경계를 임의로 합치거나 한쪽 URL을 다른 기능에 재사용하지 않습니다.

## 변경 경계

- 시장 자료 수집·정규화, 지표·전략, 백테스트, 포트폴리오 위험, PAPER 관찰, 실제 주문은 분리합니다.
- 전략은 증권사 API를 직접 호출하지 않습니다. 증권사 통신은 백엔드 adapter 또는 실행 계층만 담당합니다.
- 프런트엔드에는 증권사 인증정보를 두지 않습니다. 외부 입력·응답은 모델 또는 schema로 검증합니다.
- 실제 주문 endpoint와 증권사 주문 호출은 구현하지 않습니다. 테스트·연구는 PAPER 또는 simulation만 사용합니다.
- 연구 결과는 strict, approximate, fixture, PAPER, 실거래를 서로 다른 등급으로 표시합니다. 한 등급의 근거를 다른 등급의 성과나 승인 근거로 사용하지 않습니다.

## 새 작업 시작 순서

1. `AGENTS.md`, 이 문서, 관련 하위 `AGENTS.md`를 읽습니다.
2. `docs/worktree-tasks.md`에서 활성·차단 작업과 충돌하는 경로를 확인합니다.
3. 해당 slug의 `docs/development-records/` 기록과 최신 `HANDOFF.md`를 읽고 실제 Git 상태를 대조합니다.
4. 연구 작업은 `docs/research-mandate.md`와 JSON을 먼저 확인합니다. runner 또는 worktree 작업은 해당 운영 문서를 먼저 읽습니다.
5. 투자 개발 후속 작업은 [투자 개발 로드맵](investment-development-roadmap.md)을 먼저 읽고 해당 단계의 체크리스트·증거·의존성을 따릅니다.

완료 시에는 [개발 기록 기준](development-records.md)을 따릅니다.
