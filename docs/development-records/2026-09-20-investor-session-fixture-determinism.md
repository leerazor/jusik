# 투자자 freshness fixture 결정성 보강

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `investor-session-fixture-determinism-20260920`
- 기준/통합: `a9f88f0` / 다음 통합 커밋
- 범위: 투자자 테스트의 장외 시각 의존성을 제거했습니다. 운영 코드의 stale/fresh 정책과 거래 주문 경계는 변경하지 않았습니다.

## 변경과 결정

- `test_review_closed_takes_priority_and_watch_is_not_sell_signal`은 고정된 KRX 완료 세션 시각을 사용합니다.
- Yahoo provider fixture는 현재 시각에 따라 계산한 최신 완료 세션의 종가를 `as_of`로 사용해 주말·장외 실행에서도 결정적으로 freshness 계약을 검증합니다.
- 실제 데이터 수집, 계좌·원장·서비스·runner, PAPER/live, 주문 및 원격 저장소는 변경하지 않았습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 테스트 결정성만 보강했습니다.
- 운영 문서: 해당 없음. runner는 계속 중지 상태입니다.
- API·설정·데이터 계약: 해당 없음. stale quote를 허용하도록 완화하지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_investor.py -q` — `25 passed`
- `backend/.venv/bin/ruff check backend/tests/test_investor.py` — 통과
- canonical contract bundle — `243 passed`
- governance/runner/mandate bundle — `117 passed`
- 저장소 전체 strict mypy는 별도 canonical 명령으로 이미 통과했으며, 단일 테스트 파일을 저장소 루트에서 직접 mypy에 넘기는 명령은 패키지 경로 설정이 없어 사용하지 않았습니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·네트워크 수집·원격 push·Windows 종료 없음.
- `jusik-development-runner.service` inactive, timer disabled 상태를 유지합니다.

## 증거와 재개

- audit: 없음(테스트 fixture 변경만 수행)
- 남은 작업·차단 조건: 투자자 테스트와 무관한 경제 gate(R1-04/R1-05, R2-02/R2-03, R4+)는 자료·PIT 근거가 확보될 때까지 차단 상태입니다.
- 다음 시작: canonical contract/governance bundle을 재검증한 뒤, 실제 자료가 준비된 경제 gate만 재개합니다.
