# historical source provenance 격리 재확인

- 상태: 완료·격리 replay 준비
- 기록 시각: 2026-09-20T06:30:00Z
- 작업 slug: `historical-source-provenance-recheck-20260920`
- 기준/통합: `240f7ea` / 다음 통합 커밋
- 범위: 고정 결과의 승인 source가 Git/audit에 보존되는지 read-only로 확인했습니다. main checkout, artifact, verifier, runner는 변경하지 않았습니다.

## 변경과 결정

- portfolio bundle의 engine SHA `2a91ef9621fcb96b52179fb8fd22df7f74d6aab385b798333dd354594e61f70c`는 Git `cb1d12f2e68d370985f0e5b167a9f443edbcee88` 및 audit snapshot에서 재현했습니다.
- signal archive calendar SHA `edca750738bf69bb58b27ee15a0985a3434707ba1daad06719c26a4d17a54d9a`는 Git `c67e6e271bcb5276ab450c82965752fbd9a08364` 및 evidence snapshot에서 재현했습니다.
- 과거 source commit은 현재 accounting test가 추가되기 전 상태이므로 current test suite에 무리하게 주입하지 않았습니다. 격리 replay가 필요합니다.

## 검증

- `git rev-list --all` + `git show ... | sha256sum` — 두 승인 SHA와 commit 일치
- audit snapshot 파일 hash 대조 — 두 source 일치
- 임시 `git archive` 추출 — source 보존 확인 후 임시 디렉터리 삭제
- 현재 main 전체 회귀 결과는 별도 기록의 `1702 passed, 6 failed`를 유지하며, historical mismatch를 성공으로 재분류하지 않았습니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·network collection·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 유지.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-session-calendar-stress-v1-2cb9ec646e18470a8267ef06742562d2` 및 `paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39`
- 남은 작업: 승인 source commit으로 별도 격리 replay harness를 만들지, 현재 artifact를 차단 상태로 유지할지 결정해야 합니다. 현재 경제 성과에는 사용하지 않습니다.
- 다음 시작: R1-04 SEC operator facts 또는 R2 비용/FX 원천 자료가 준비됐는지 확인하고, historical replay는 그 의존성을 방해하지 않는 bounded 작업으로만 진행합니다.
