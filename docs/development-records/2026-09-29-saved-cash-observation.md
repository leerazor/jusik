# 저장 현금 관측 일관성 검증

- 상태: 기술 완료; 투자 평가 미실시.
- 작업 slug: `lab-discovery-c23e56fa96638e6051ef45a964d77a02`.
- 통합: 로컬 `main` `1df398c510ecccdc6f65b4d6655b56ee1827371e`.
- 범위: 오프라인 회계 진단의 저장 현금 관측과 회귀 테스트만 수정했습니다.

## 변경과 결정

`account_result()`가 각 equity 행의 `cash_native * fx_krw_per_usd`와 저장된 `cash_krw`를 대조합니다. 저장 전략의 Decimal 정밀도 28과 반올림을 재현해 정상 행의 계산 차이를 오판하지 않습니다. 모순된 행은 `available` 현금 근거로 사용하지 않고 거부합니다. 원자료나 전략·투자 기준은 바꾸지 않았습니다.

## 문서·계약 영향

회계 진단의 입력 무결성만 강화했습니다. 사용자 화면·설정·운영 절차는 바뀌지 않아 별도 기능 문서는 수정하지 않았습니다.

## 검증

- 작업자 통합 전후 focused pytest 각 50개 통과. runner의 독립 완료 검토 후 작업 상태 `completed`, `ENGINEERING_COMPLETE/NOT_EVALUATED`.
- 현재 `main`에서 두 관련 테스트 파일과 Sortino 테스트를 함께 재실행: 91 passed.
- 현재 `main`의 관련 4개 파일 Ruff check/format 및 strict mypy 통과.
- 증거: `/home/kwl/.local/share/jusik/roadmap-development-runner/attempts/a35e03aff07546189e508907b62f6e49/`.

## 안전·재개

시장 자료, 주문, PAPER/live, 원격 push는 변경하지 않았습니다. 비용 포함 손익의 실제 평가는 완전한 체결·자료·비용 근거 확보 전까지 `NOT_EVALUATED`입니다.
