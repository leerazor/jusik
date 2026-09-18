# 개발 문서 연속성 정비

- 상태: 완료
- 기록 시각: 2026-09-14T23:36:21Z
- 작업 slug: `documentation-continuity`
- 기준/통합: `8521268` / 이 문서 변경을 포함한 후속 문서 커밋
- 범위: 다음 AI agent가 개발을 재개할 수 있는 문서 경로와 완료 기록 기준을 추가했습니다. 기존 제품 동작, 연구 정책, 실행기, PAPER·실주문 경계는 변경하지 않았습니다.

## 변경과 결정

- `docs/architecture.md`에 포트폴리오 백엔드, 연구 백엔드, 프런트엔드, 개발 실행기의 경계와 새 작업 시작 순서를 추가했습니다.
- `docs/development-records.md`에 영구 작업 기록, 작업 등록부, 짧은 handoff, 외부 audit의 역할과 기록 양식을 정의했습니다.
- `AGENTS.md`, `docs/worktree-workflow.md`, `README.md`가 새 문서와 완료 절차를 가리키게 했습니다.
- `HANDOFF.md`는 현재 재개 상태만 유지합니다. 완료 작업의 상세 이력은 저장소의 개발 기록과 외부 audit에 둡니다.

## 문서·계약 영향

- 사용자 문서: `README.md`에 개발 문서 시작점을 추가했습니다.
- 운영 문서: `docs/worktree-workflow.md`에 개발 기록 경로와 완료 절차를 추가했습니다.
- API·설정·데이터 계약: 변경 없음. 구조 안내에는 기존 두 백엔드 URL 경계를 명시했습니다.

## 검증

- `git diff --check` — 통과.
- 테스트·린트·타입 검사 — 문서 전용 변경이라 실행하지 않았습니다.

## 안전·운영 상태

- PAPER·실주문, 서비스, 데이터, 배포, 원격 push 변경 없음.
- 시작부터 있던 `docs/agent-tooling.md` 수정, `HANDOFF.md`, `docs/research-ui-redesign.md`, `.serena/`는 보존했습니다.

## 증거와 재개

- audit: 없음.
- 남은 작업·차단 조건: 기존 누적 `HANDOFF.md`는 보존했습니다. 이후 완료 작업부터 현재 재개 상태만 남기도록 운영해야 합니다.
- 다음 시작: 실제 Git 상태를 확인한 뒤, 완료한 각 slug의 개발 기록을 이 기준으로 작성합니다.
