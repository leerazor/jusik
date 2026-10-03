# 등록 종목 순수 보유 합성 회계 기준선

- 상태: 구현 완료, 독립 검토·로컬 main 통합 대기
- 기록 시각: 2026-10-03T12:50:37Z
- 작업 slug: `approved-buy-hold-reference-20261003`
- 기준/통합: `64391c8` / 없음
- 범위: frozen 합성 입력의 순수 보유 회계. 실제 자료 adapter·cap-control·후보·운영 경로 제외.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: 단일 통화 기업행동 전이를 종목별로 재사용하고, 총 1억원 예산의 첫 공식 시가 매수·명시 비용/과세·원화 NAV·레버리지와 낙폭 위반을 계산한다. 분할과 배당 ex가 같은 시각이면 분할 수량으로 권리를 계산한다. 마지막 평가시각을 별도 기록한다.
- `backend/tests/test_approved_universe_buy_hold.py`: KR+US 독립 손계산 oracle, 동시 분할/배당, 종료시각 FX, 미래 FX 배제와 결손/중복/비원시가격/소수 분할 거부를 검증한다. 합성 oracle의 원화 NAV 116,100,600원은 회계 예시이며 실수익률이 아니다.
- 독립 검토 P1 수정: 동일 시각의 split→ex→payment→open→close 전이를 모두 적용한 뒤 NAV·위험을 한 번 기록한다. 초기 1억원 peak는 유지하며 개별 거래·배당 원장은 그대로 남긴다. 상쇄되는 두 종목 종가와 배당 ex/시가의 허위 낙폭을 회귀로 막고 실제 25% 손실 위반을 확인했다.
- 독립 검토 P2 수정: 적격 FX를 유효 시각 우선, 동일 유효 시각에서는 가용 시각 최신 수정본 우선으로 선택한다. 늦게 도착한 과거 유효 시각 관측치가 현재 환율을 덮지 않도록 회귀로 고정했다.

## 문서·계약 영향

- 사용자 문서: `docs/research.md`에 오프라인 입력·출력과 검증 한계를 기술했다.
- 운영 문서: 해당 없음. 서비스·실행기 변경 없음.
- API·설정·데이터 계약: 저장소 API나 설정은 변경하지 않았다. 새 typed Python 함수 계약만 추가했다.

## 검증

- `PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/pytest -q -p no:cacheprovider backend/tests/test_approved_universe_buy_hold.py backend/tests/test_market_history_action_accounting.py` — 67개 통과.
- `RUFF_CACHE_DIR=/tmp/buyhold-ruff backend/.venv/bin/ruff check backend/jusik/approved_universe_buy_hold.py backend/tests/test_approved_universe_buy_hold.py` 및 `backend/.venv/bin/ruff format --check backend/jusik/approved_universe_buy_hold.py backend/tests/test_approved_universe_buy_hold.py` — 통과.
- `PYTHONPATH=backend MYPY_CACHE_DIR=/tmp/buyhold-mypy backend/.venv/bin/mypy --strict backend/jusik/approved_universe_buy_hold.py backend/tests/test_approved_universe_buy_hold.py` — strict 검사 통과.
- 독립 `/tmp/buyhold-independent-oracle.py backend/jusik` 및 `/tmp/buyhold-independent-boundaries.py` — 합성 예상/실제 NAV 116,100,600원, 현금 KRW 921,000/USD 833, 매수 4,950/490 일치. 미래 FX 배제와 종료시각 평가도 통과. 저장소 밖 임시 oracle은 정식 연구 입력이 아니다.

## 안전·운영 상태

- 주문, PAPER/live, DB, 서비스, 원격 push, credential 및 실제 데이터 조회 변경 없음.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 각 입력 pin은 함수 입력 계약이며 실제 원천 진위 검증이 아니다.
- 남은 작업·차단 조건: P1/P2 수정본의 독립 재검토·로컬 main 통합. 실16종목 adapter와 원천/달력/PIT/비용 인수 전에는 실제 성과 계산 차단.
- 다음 시작: 이 작업 브랜치의 수정 커밋을 독립 재검토한 뒤 supervisor가 로컬 main에 순차 통합한다.

- workflow 판단: 도움 됨 — 기존 회계 전이와 규약을 먼저 재사용해 회계 결함을 좁혔다.
- 근거: 독립 oracle이 동일시각 분할/배당 순서 결함을 찾아 수정했고 회귀검사로 고정했다. 시간·호출 절감은 미측정.
- 다음 조정: 유지 — 좁은 합성 회계 단위의 독립 대사를 다음 단계에도 적용한다.
