# Alpaca SIP 가격 증거 준비

- 상태: 구현 완료, 연구 자료 인수 미완료. 작업 slug `alpaca-price-evidence-20261002`; 기준 `a318272`.
- 범위: 기존 수집기·캐시·mandate·거래 경로를 수정하지 않고 [독립 CLI](../alpaca-price-evidence.md)와 집중 회귀만 추가했다. 사용자 계약은 명시 입력 해시, 신규 출력 경로, 오프라인 증거 전용 네 파일이다.
- [고정 입력](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/scope.json) 8개 해시와 [최종 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/binding.json)을 확인했다. SIP `1Day/raw`, 날짜 범위, 페이지 완료, 단건 RAPT 일치, 뉴욕 세션 자정, 십진 OHLCV·중복·고정 272세션을 검사한다. 성공 파일은 임시 형제 디렉터리에서 작성한 후 게시한다.
- 실제 고정 원문: 22종목 중 9종목 1,683봉, 응답 0봉 7종목, 별도 미조회 6종목, RAPT 138봉 일치, 0거래량 84봉 유지. [세션 결손](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/missing-sessions.json)은 원인 추정 없이 분류했다.
- 검증: `backend/.venv/bin/pytest -q backend/tests/test_alpaca_price_evidence.py` 15 passed; `backend/.venv/bin/ruff format --check`와 `ruff check` 대상 2파일 PASS; `backend/.venv/bin/mypy --strict` 대상 2파일 PASS. 고정 원문 CLI 1회 성공, 시장 네트워크 0회. 기존 전체 suite와 frontend build는 변경 영향이 없어 반복하지 않았다.
- 경계: `evidence_only`; 역사적 `available_at`을 생성하지 않는다. 신원·사건 관측시각·수익 성과 적격성은 검증되지 않았다. 주문·배포·추가 결제·자격증명 변경은 없다.
- workflow 판단: 고정된 수집 원문을 재요청하지 않고 단일 CLI로 재사용한 경로가 이번 좁은 증거 준비에 적합했다.
- 근거: 1회 최종 자료 변환과 15개 집중 테스트, 외부 요청 0회. 시간·비용 절감량은 측정하지 않았다.
- 다음 조정: 현재 출력을 연구 입력으로 연결하기 전에 종목/상품 동일성, 사건 관측·가용시각, 결손 원인과 비용·FX·NAV 계약을 별도 범위에서 검증한다.
