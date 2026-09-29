# Sortino NAV 시간 순서 검증

- 상태: 기술 완료; 투자 평가 미실시.
- 작업 slug: `lab-discovery-fde5cf20f1f6c53cbb17b296d969f054`.
- 통합: 로컬 `main` `611c817d7190e6b72dbd33428692c793d4550622`.
- 범위: 오프라인 Sortino 계산의 NAV 시각 입력과 회귀 테스트만 수정했습니다.

## 변경과 결정

`sortino_from_nav()`가 시간대 없는 시각, 중복 시각, 역순 시각에 대해 수치를 반환하지 않고 `unavailable`과 원인 코드를 반환합니다. 유효한 NAV의 계산식과 투자 기준은 유지했습니다. 합성 입력 결과를 전략 성과로 해석하지 않습니다.

## 문서·계약 영향

계산 API의 입력 거부 조건만 강화했습니다. 사용자 화면·설정·운영 절차는 바뀌지 않아 별도 기능 문서는 수정하지 않았습니다.

## 검증

- 작업자 통합 전후 focused pytest 각 41개 통과. runner의 독립 완료 검토 후 작업 상태 `completed`, `ENGINEERING_COMPLETE/NOT_EVALUATED`.
- 현재 `main`에서 두 관련 테스트 파일과 현금 회계 테스트를 함께 재실행: 91 passed.
- 현재 `main`의 관련 4개 파일 Ruff check/format 및 strict mypy 통과.
- 증거: `/home/kwl/.local/share/jusik/roadmap-development-runner/attempts/e781f6396abd4096babbab09e78e75c5/`; 작업 인계: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-sortino-time-fde5cf20/HANDOFF.md`.

## 안전·재개

시장 자료, 주문, PAPER/live, 원격 push는 변경하지 않았습니다. 실제 Sortino 성과 평가는 필요한 입력 자료와 별도 투자 검증 전까지 `NOT_EVALUATED`입니다.
