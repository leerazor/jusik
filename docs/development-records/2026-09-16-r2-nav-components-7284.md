# 저장 NAV 구성요소 진단

- 상태: 복구 구현 완료·통합 대기
- 기록 시각: 2026-09-16T00:00:00Z
- 작업 slug: `r2-nav-components-7284`
- 기준/통합: `be8a85dd34c42e825638ac282a530880decdcec3` / 없음
- 범위: 저장 `result.equity`의 Decimal residual 진단과 별도 coverage artifact, 오프라인 CLI·fixture·한국어 계약을 추가했습니다. calendar·독립 회계·경제 평가와 R2-05 전체 checkbox는 변경하지 않습니다.

## 변경과 결정

- `backend/jusik/research_nav_reconciliation.py`: 고정 SHA 검증, 중복 키 차단, bounded JSON/Decimal 파싱, canonical chronological session 검증, residual/coverage artifact 생성 및 CLI를 추가했습니다.
- `backend/tests/test_research_nav_reconciliation.py`: 계획된 fixture inventory와 CLI·구조·중복 키 검사를 추가했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/research-nav-reconciliation.md`에 CLI와 artifact 계약을 기록했습니다.
- 운영 문서: 해당 없음. 서비스·DB·설정·주문을 추가하지 않습니다.
- API·설정·데이터 계약: 저장 run 입력 계약과 진단 artifact schema를 새 문서에 기록했습니다.

## 검증

- 최초 구현 검증: focused pytest, Ruff, configured strict mypy는 작업자 로그에 실행 결과를 기록하기로 했으며, 당시 기술 acceptance는 완료되지 않았습니다.
- 저장 US run: 최초 기록은 고정 SHA 대조 후 1회 실행 예정 상태였고, 복구에서는 새 검사 후 실제 동결 pilot을 1회 실행했습니다.

## 안전·운영 상태

- 네트워크, simulation/replay, GPU, PAPER/live, 주문, DB, 서비스, 원격 push는 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-05-7284d056/worker/`; manifest: 감독이 생성
- 남은 작업·차단 조건: Terra 독립 review와 supervisor 통합이 남았습니다. calendar completeness와 경제 평가는 각각 unavailable/not-evaluated입니다.
- 다음 시작: 독립 review에서 네 파일 diff와 저장 run artifact의 SHA·행 수·최대 residual을 확인합니다.

## 복구 기록

- 복구 범위: 원본 archive의 네 파일을 보존한 상태에서 JSON UTF-8 오류의 exit `2` 변환, 쓰기 전 입력·두 artifact 경로 별칭 검사, finite Decimal exponent의 strict typing, 경계값·artifact 계약 회귀 검사를 추가했습니다.
- 과거 기록 보존: 이전 구현의 24개 fixture·동일 실패 이력·검증 전 완료 표현은 이 기록의 앞부분과 외부 audit에 그대로 보존합니다. 새 복구 검증은 bounds64 named scenario 및 누적 wall/CPU 1800초, 동일 원인 수정·재검증 최대 3회 조건을 적용합니다.
- 완료 표현 정정: 앞서 기록된 `완료`는 검증 전 표현이므로 기술 acceptance 완료를 뜻하지 않는 historical source로 구분하고, 현재 상태를 복구 구현 완료·통합 대기로 표시합니다.
- 검증 상태: 복구 focused pytest·Ruff·configured strict mypy가 통과했으며, Terra review·local main 통합 검증은 supervisor가 수행할 작업으로 남아 있습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-nav-recovery/worker/`에 inventory와 명령별 raw output·exit·wall·CPU를 보관합니다.
