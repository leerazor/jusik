# Canonical governance sync recheck

- 기록 시각: 2026-09-20T03:05:00Z
- `validate_mandate(Path('.'))` 성공:
  - digest `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`
  - `policy_version=investment-roadmap-governance-v1`
  - `dispatch_enabled=true`
- `load_roadmap(Path('.'))` 성공: checklist `40`, complete `16`, roadmap content digest
  `3de9bf844542d12ce494b69e1c5203d6a4fdd165d6e52f82a9718e12f46f9908`.
- `docs/research-mandate.json` bytes SHA-256은 동일 digest로 확인했습니다.
- runner DB는 `blocked=9`, `completed=75`, `failed=12`, `running=0`; user service `inactive`, timer
  `not-found`입니다.

## 현재 재확인 (2026-09-20T05:05:19Z)

- `docs/research-mandate.json` SHA는 동일한
  `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`이며, fragment hash를
  포함한 legacy manifest도 governance 테스트의 정본 규칙으로 검증했습니다.
- mandate/roadmap/runner planning focused pytest는 `57 passed`입니다. 현재 user service는
  `inactive`, timer는 `disabled`이며 자동 resume은 수행하지 않았습니다.

## 판정

- 승인 설계·mandate·로드맵 parser의 현재 동기화와 fail-closed 운영 상태를 재현했습니다.
- 자동 dispatch/resume, 성과 승격, PAPER/live, remote push, Windows 종료는 수행하지 않았습니다.
