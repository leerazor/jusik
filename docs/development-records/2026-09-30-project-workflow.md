# 프로젝트 workflow 정리

- 상태: 완료
- 기록 시각: 2026-09-30T07:34:23.706700+00:00
- 작업 slug: `project-workflow-20260930`
- 기준: `59eeac7dce8bb80f8f65b4d497a8e3880c19abe5`; 통합: 이 문서를 처음 추가한 main 커밋(`git log --diff-filter=A --format=%H -- docs/project-workflow.md`로 확인).
- 범위: 운영 규칙 문서 편집. 기존 agent 실행 규칙을 옮기고 작업 경로·유용성 평가를 안내한다.

## 변경과 결정

- `docs/project-workflow.md`에 시작→범위→수행→검증→기록 흐름과 상황별 원본 링크를 정리했다.
- AGENTS.md의 agent 구성·순서·병렬화 규칙은 내용 변경 없이 새 문서로 이동했다. 루트 지침과 MEMORY.md에서 시작할 때 참조하도록 연결했다.
- 별도 점수표·자동화·정기 보고를 만들지 않고 기존 개발 기록에 유용성 판단을 남긴다.
- 작은 운영 지침 편집으로 직접 main에서 처리했다. worktree 운영 문서의 운영 규칙 편집 구분을 적용했으며 코드 개발 역할 체인은 실행하지 않았다.

## 문서·계약 영향

- 운영 문서: AGENTS.md, MEMORY.md, docs/project-workflow.md.
- API·설정·데이터·사용자 화면 계약: 변경 없음.

## 검증

- `git diff --check` 및 Markdown 상대 링크의 파일·anchor 확인.
- 이동 전후 agent 규칙 본문 비교: 상대 링크 조정 외 동일한지 확인.
- 앱 테스트·빌드: 코드 변경이 없어 실행하지 않음. 독립 agent 검토는 수행하지 않음.

## workflow 유용성

- workflow 판단: 아직 미확인 — 문서 탐색과 중복 규칙을 줄이는 목적.
- 근거: 기존 agent 규칙을 복제하지 않고 이동하고 정본 링크를 제공했다. 실제 시간·호출 절감은 미측정.
- 다음 조정: 다음 실제 작업에서 참조 유용성과 불필요한 단계를 확인하고 필요한 경우 수정한다.

## 안전·재개

- runner는 시작부터 paused, running 0, service/timer inactive였다. pause·service 중지를 확인했으며 다른 수동 연구가 진행 중이므로 기존 정지 상태를 유지한다.
- 생산 코드·자료·주문·배포·원격 push 변경 없음. 기존 미추적 HANDOFF.md와 다른 worktree는 보존했다.
- 인계: [작업별 인계](../handoffs/2026-09-30-project-workflow.md). 산출물 구현에 남은 작업 없음; 효과 검증은 후속 실제 작업에서 수행한다.
