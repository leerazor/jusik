# Runner dirty worktree gate 복구

자동 timer의 cycle이 `tracked worktree is dirty`로 fail-closed 된 원인을
worktree별로 확인했다. cadence stale worktree의 미커밋 변경은 main에 이미
반영된 `_manifest_paths` 정리와 source-path regression이어서 검증 후 해당
branch에 기록 커밋(`1a7edd6`)하고 main에 선별 통합했다(`df59edc`, `d806da1`).
corrected-calendar worktree의 변경도 main에 이미 반영된 bundle/calendar identity
등록과 동일함을 확인한 뒤 보존 커밋(`6d58357`)으로 dirty 상태만 해소했다.

- cadence focused pytest 16개, Ruff, strict mypy 통과
- root `HANDOFF.md`는 runner 예외 규칙에 따라 보존
- 다음 timer cycle은 `status=idle`, exit 0으로 종료
- 사용자 변경 가능성이 있는 KOFR worktree와 volatility stale worktree는 수정·삭제하지 않음
