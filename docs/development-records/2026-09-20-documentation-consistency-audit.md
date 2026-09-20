# Documentation consistency audit

- 상태: 완료
- 기록 시각: 2026-09-20T12:00:00Z
- 작업 slug: `documentation-consistency-audit-20260920`
- 기준/통합: `ec1c4c2` / 다음 통합 커밋
- 범위: 최근 SEC action/exclude, KIS BanKIS 비용 선택, KRX key probe와 저장소 최신 커밋이 작업 등록부·개발 기록과 일치하는지 점검하고 누락된 상태를 보완했습니다. 사용자 소유 미추적 `HANDOFF.md`는 수정하지 않았습니다.

## 변경과 결정

- `docs/worktree-tasks.md` 최상단 작업에 SEC `ready=true`, KIS A 선택, `KRX_API_KEY` 일별시세 HTTP 200, 별도 KRX status 권한 대기를 명시했습니다.
- SEC 기록의 이전 “미완성 form” 표현과 KIS 범위 미확정 표현을 현재 검증 결과에 맞게 고쳤습니다.
- KRX 키 값은 출력·기록하지 않고 변수명과 성공 여부만 기록했습니다.

## 검증

- 저장소 최신 커밋과 task/record 경로 대조 — 통과
- KRX `KRX_API_KEY` 일별시세 bounded request — HTTP 200; 응답 원문은 기록하지 않음
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 유지.

## 다음 시작

- KRX Open API 서비스 목록에서 현재 키의 status/issue dataset 권한을 확인하고, 권한이 있으면 29개 종목·2026-06-29 bounded query를 실행합니다. 권한이 없으면 사용자에게 추가 신청이 필요한지 한 번만 보고합니다.
