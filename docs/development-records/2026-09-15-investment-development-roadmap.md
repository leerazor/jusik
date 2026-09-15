# 투자 개발 로드맵

- 상태: 완료
- 기록 시각: 2026-09-15T02:15:40Z
- 작업 slug: `investment-development-roadmap`
- 기준/통합: `c2ada5c` / `1d6ebfce1ecf2620a0c670e24866e5608f67572a`
- 범위: 미래 투자 개발 계획, 단계별 체크리스트, 경제 목표 평가, 증거 추적, 병렬 개발·통합 기준을 문서화했습니다. 코드·전략·mandate·실행기·거래 정책은 변경하지 않았습니다.

## 변경과 결정

- `docs/investment-development-roadmap.md`에 미국 `-16.93%` 손실 진단을 우선하는 R0~R7 계획을 작성했습니다.
- 기술 완료와 경제적 목표 평가를 분리하고, 양의 순수익·DD20·비용·회전율은 관찰 목표로만 남겼습니다.
- R0 공통 계약 후 R1 데이터, R2 독립 손실 회계, R3 기존 자료 UI를 병렬화하고 R4 이후 단계를 순차화했습니다.
- 각 checklist ID를 후속 ticket 단위로 등록하고, 첫 착수는 R0-01~R0-05로 제한하도록 했습니다. R4는 R1/R2와 독립 review만 연구 계산의 선행 조건으로 둡니다.
- `run.status=completed` 선행 조건 아래 strict의 `result.status=ready/completeness=complete`와 approximate의 `result.status=approximate/completeness=approximate` 자료 gate를 구분하고, same market/grade·고정 가정·policy/data contract hash·source simulated 조건을 확인하며 3년 입력은 별도 수집하도록 했습니다.
- `docs/architecture.md`의 새 작업 시작 순서에 로드맵 링크와 읽기 조건을 한 줄 추가했습니다.

## 문서·계약 영향

- 사용자 문서: 새 로드맵은 후속 작업의 목표·체크리스트 문서입니다.
- 운영 문서: 구조 안내에 로드맵 발견 링크를 추가했습니다. worktree registry는 감독 소유이므로 이 작업에서 수정하지 않았습니다.
- API·설정·데이터 계약: 실제 계약 변경 없음. 로드맵에서 향후 R0가 계약을 정의하도록 계획만 기록했습니다.

## 검증

- `git diff --check` — 통과.
- 문서 링크, 체크리스트 ID, 단계 의존성, 줄 수와 허용 경로를 독립적으로 확인 — 통과.
- 작업/통합 main 문서 검사: 미래 체크 ID 40개 모두 미완료, 단계 8개, 로컬 링크 2개 통과. 독립 review는 `08aee0e`의 재현·기업행사·등급별 final 기준과 병렬 소유권을 확인했으며 중요 지적이 없습니다.
- 이전 미국 산출물의 두 SHA-256을 재확인했습니다. 수익률을 재실행하거나 새 자료를 수집한 것은 아닙니다.
- 테스트·lint·type check·build — 코드 변경이 없는 문서 작업이므로 실행하지 않습니다.

## 안전·운영 상태

- PAPER·실주문, brokerage API, 서비스, 연구 데이터베이스, 외부 배포와 원격 push 변경 없음. 자동 runner는 pause를 확인·유지했으며 service/timer가 inactive임을 확인했습니다.
- 비밀정보·인증정보·계좌 식별자·원시 provider 응답을 기록하지 않았습니다.
- 기존 사용자 변경과 작업 등록부, AGENTS, agent-tooling, research mandate, 코드는 보존했습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-investment-development-roadmap`; `baseline-evidence.json`에 기존 artifact 해시 확인, `validate_docs.py`에 문서 검사 절차를 보존합니다. 기준 연구 증거는 기존 live-contract-fixes audit에 있습니다.
- manifest: 기존 `us-pilot-1y-stable.json`과 `us-web-pilot-run.json`은 로드맵에 해시로만 참조했습니다.
- 남은 작업·차단 조건: 모든 R0~R7 기능 체크리스트는 미완료이며, 실제 후속 작업의 테스트·독립 review·main 통합이 필요합니다.
- 다음 시작: R0-01부터 기준 manifest·결과 계약·deterministic replay 계획을 실제 작업 등록부와 대조합니다.
