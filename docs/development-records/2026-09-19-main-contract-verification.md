# Main 계약 재검증 기록

- 상태: 검증 완료. 제품 코드와 연구 입력은 변경하지 않았습니다.
- 기준 main: `d6ac5b4`.
- 대상: 성과 지표, portfolio engine, time-evidence, market calendar, forward read API의 관련 테스트와 source 계약.

## 확인 결과

- 프로젝트 전용 `backend/.venv`에 고정 의존성 `exchange_calendars==4.12`가 없어 최초 수집이 중단되었습니다. 전역 환경은 변경하지 않고 해당 venv에만 의존성과 전이 패키지를 설치했습니다.
- 동일 5개 테스트 파일 통합 실행: **89 passed**, 2개 기존 deprecation warning, 9.98초.
- Ruff check: 통과.
- configured strict mypy 대상 5개 source: 통과.
- 실제 broker 주문, PAPER/live 전환, network market-data 수집, 운영 DB·서비스·remote 변경: 0회.

## 제한과 다음 재개 조건

- KOFR 후보의 기술 검사·독립 리뷰는 통과했지만 archive 보조 스크립트 실패로 runner 상태는 차단입니다. 공식 KOFR/raw receipt와 금융 acceptance가 없으므로 후보를 main에 병합하지 않습니다.
- roadmap runner에는 실행 가능한 queued/running 작업이 없습니다. 실제 provider receipt·가격·권리·UTC 경계 자료가 준비되기 전까지 경제 평가와 OOS 승격은 fail-closed로 유지합니다.
- 기존 untracked 루트 `HANDOFF.md`와 다른 작업자의 미완료 worktree는 보존합니다.

