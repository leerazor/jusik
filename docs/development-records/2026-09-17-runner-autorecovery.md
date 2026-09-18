# 자동 개발 재개와 제한된 오류 복구

- 상태: 구현·통합 완료, 기록 저장 후 운영 재개.
- 기록 시각: 2026-09-16T21:21:00Z; 작업 slug: `runner-autorecovery`.
- 기준/통합: `9ab0b6c` / `360f6af0339df5abfcc83b31ee46caf20c7b5a59`.
- 범위: 실행기 큐·재시도·자식 캐시와 실행 지침. 투자 조건·전략·성과 수치는 변경하지 않았습니다.

## 변경과 결정

과거 blocked 작업 8개가 roadmap planning의 대기 상한을 채워 새 작업 등록을 막았습니다. roadmap은 queued/running만 계산하며 research의 기존 정책은 유지합니다. 자식은 현재 attempt 아래의 XDG/uv/pip/Ruff/mypy 캐시를 사용합니다.

`automatic_recovery`는 기본 false입니다. 설치된 roadmap만 활성화합니다. 명시된 환경·구현 오류와 교정 가능한 planner 출력 오류는 같은 작업에서 최대 두 번, 60초·120초 대기 후 재시도합니다. 종료 기록과 재시도 예약은 하나의 transaction으로 저장합니다. 오래된 일반·planner callback은 현재 시도를 덮거나 새 제안을 등록할 수 없습니다.

허용 사유는 고정 label로 제한하고, 자료 부족·금융 정책·identity/hash 오류·일반 검토 실패는 자동 복구하지 않습니다. 성공 판정은 기존 검사·독립 검토·증거·통합 계약을 유지합니다. 실행 지침에는 소유 환경 복구, 이전 worktree 재사용과 과거 중단의 해석을 명시했습니다.

## 문서·계약 영향

- 운영 문서: `docs/development-runner.md`의 설정·재시도·격리 정책을 갱신했습니다.
- 설정/결과 계약: 기본 false `automatic_recovery`, nullable `recovery_kind` 추가. 기존 completion 생략은 None입니다. DB migration은 없습니다.
- 사용자 UI/API와 투자 데이터 계약: 변경 없음.

## 검증

- worker와 main: runner/planning/roadmap focused pytest — 95 passed.
- 변경 모듈·관련 테스트 Ruff check/format, 설정된 strict mypy, `git diff --check` — PASS.
- fake child와 임시 SQLite로 retry 한도·backoff·재시작·marker·stale callback·queue cap을 검증했습니다. 실제 Codex/service/주문을 테스트에 사용하지 않았습니다.
- 독립 review 중요 지적 해소. 전체 suite와 frontend build는 변경 범위 밖이라 실행하지 않았습니다.
- code route helper는 늦은 settings 경계 때문에 기존 turn_context를 제외해 실패했습니다. 원본 로그를 보존하고 같은 helper의 child-owned thread/turn-id 방식으로 Luna를 확인했습니다. reviewer native 감사는 PASS입니다.

## 안전·운영 상태

수동 개발 중 roadmap runner를 pause하고 service를 중지했습니다. timer는 유지했습니다. 기록 커밋 후 기존 R2-06을 명시적으로 retry하고 roadmap 자동 복구를 활성화합니다. 실제 활성화 증거는 아래 외부 파일에 저장합니다. 옛 research 설정은 paused 유지합니다. 실주문·PAPER 활성화·운영 거래 데이터·원격 push는 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-runner-autorecovery`.
- `source-manifest.json`, `integration.json`, `worker/*v3*`, `review.md`, `code-routing-supplemental.json`이 최종 소스·검사·검토 근거입니다. 초기 결과도 보존했습니다.
- 전용 runner worktree/branch는 보관·검증 후 제거했습니다. R2-06의 기존 worktree와 준비된 전용 venv는 보존했습니다.
- 다음 시작: `HANDOFF.md`, `activation.json`과 현재 runner 상태를 대조합니다. 자동 실행 중 main을 수동 수정하지 않습니다. 수익률 개선은 이번 작업에서 검증하지 않았습니다.
