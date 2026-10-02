# Alpaca SIP 가격 증거 준비

- 상태: local main 통합·검증 완료, 연구 자료 인수 미완료. 작업 slug `alpaca-price-evidence-20261002`; 기준 `a318272`.
- 범위: 기존 수집기·캐시·mandate·거래 경로를 수정하지 않고 [독립 CLI](../alpaca-price-evidence.md)와 집중 회귀만 추가했다. 사용자 계약은 명시 입력 해시, 신규 출력 경로, 오프라인 증거 전용 네 파일이다.
- [고정 입력](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/scope.json) 8개 해시와 [최종 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/binding.json)을 확인했다. SIP `1Day/raw`, 날짜 범위, 페이지 완료, 단건 RAPT 일치, 뉴욕 세션 자정, 십진 OHLCV·중복·고정 272세션을 검사한다. 성공 파일은 임시 형제 디렉터리에서 작성한 후 게시한다.
- 실제 고정 원문: 22종목 중 9종목 1,683봉, 응답 0봉 7종목, 별도 미조회 6종목, RAPT 138봉 일치, 0거래량 84봉 유지. [세션 결손](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/missing-sessions.json)은 원인 추정 없이 분류했다.
- 검증: `backend/.venv/bin/pytest -q backend/tests/test_alpaca_price_evidence.py` 15 passed; `backend/.venv/bin/ruff format --check`와 `ruff check` 대상 2파일 PASS; `backend/.venv/bin/mypy --strict` 대상 2파일 PASS. 고정 원문 CLI 1회 성공, 시장 네트워크 0회. 기존 전체 suite와 frontend build는 변경 영향이 없어 반복하지 않았다.
- 경계: `evidence_only`; 역사적 `available_at`을 생성하지 않는다. 신원·사건 관측시각·수익 성과 적격성은 검증되지 않았다. 주문·배포·추가 결제·자격증명 변경은 없다.
- workflow 판단: 고정된 수집 원문을 재요청하지 않고 단일 CLI로 재사용한 경로가 이번 좁은 증거 준비에 적합했다.
- 근거: 1회 최종 자료 변환과 15개 집중 테스트, 외부 요청 0회. 시간·비용 절감량은 측정하지 않았다.
- 다음 조정: 현재 출력을 연구 입력으로 연결하기 전에 종목/상품 동일성, 사건 관측·가용시각, 결손 원인과 비용·FX·NAV 계약을 별도 범위에서 검증한다.

## 통합·독립 검토

- 구현 `62dd8c0dd080c2b0c8ed7f1af03674299d587e26`, 통합 `e94cdbcbc3d030489e8969878d54fe92fb4db74c`; 독립 review PASS. 발견된 출력 경합은 Linux `renameat2(RENAME_NOREPLACE)`와 회귀 테스트로 해결했다.
- main에서 pytest 15개, Ruff check/format, strict mypy 2파일, diff 검사 통과. 보호8·달력·최종 코드 해시 일치. 같은 실제 원문 CLI는 main에서 재실행하지 않고 최종 산출물·코드 hash를 대조했다. `main-integration.json`, `review.json`에 증거를 보존했다.
- audit에 결과·환경 lock을 보존하고 미병합 변경·작업 프로세스가 없는 worktree와 branch를 제거했다(`cleanup.json`). runner는 tracked clean 후 복원하며 실제 상태는 `runtime-after.json`에 남긴다. 원격 push·주문·PAPER/live·배포 없음.
