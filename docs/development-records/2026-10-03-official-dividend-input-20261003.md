# 공식 현금 배당 입력 동결

- 상태: 독립 재검토·main 통합·실자료 및 회계 대사 완료
- 기록 시각: 2026-10-03 UTC
- 작업 slug: `official-dividend-input-20261003`
- 기준/통합: `5b97061c0130f844ba78fc519a90fca33e779e11` / `dd3f01f1b5c0589e0fb0a2ace52c41e6c1213e0e`; 구현 최종 `c509a794`, 병합 직전 main `64a5870`.
- 범위: 승인 종목의 현행 공식 배당 검토 사실을 독립 오프라인 JSON으로 검증·동결. 기존 검토 적격 판정·overlay·원장은 보존.

## 변경과 결정

- `backend/jusik/research_official_dividend_input.py`: 승인 목록의 전체 snapshot과 사건별 현재 공급자 revision/content SHA·최신 review ID를 검증한다. 수집 attempt의 원문 SHA·성공 상태·종목과 parser 사건 일치, 사건/revision ID 불변식, 저장된 payload SHA, 검토 내용 hash/ID, 공식 원문 bytes SHA, 신원 근거 파일 SHA와 URL을 재검증한다. 금액 외 비교 충돌·필수 사실 결손을 거부하고 금액 충돌은 원래 strict status와 정확한 Decimal 차액을 보존한다.
- 출력은 canonical JSON의 전체 bytes SHA 파일명과 O_EXCL로 동결한다. 기존 파일은 byte 일치 시만 재사용한다. 후향/PIT·원장·NAV 플래그를 명시한다.
- SQLite 두 DB 간 원자적 snapshot은 없으므로 별도 복사본을 권장하고, 두 번의 새 읽기 transaction으로 pin 변화를 재검사한다. 검토자의 신원 판단과 원문 의미를 자동 입증하지 않는다.

## 문서·계약 영향

- 사용자·입력 계약: `docs/research.md`에 manifest v1 예시, CLI 호출, 산출물 의미와 신뢰 경계를 추가했다.
- 운영 문서/API: 변경 없음. 오프라인 CLI이며 서비스·UI는 연결하지 않았다.

## 검증

- `PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests/test_research_official_dividend_input.py` — 24건 통과. 일치·금액 충돌·idempotence·pin/원문/신원/날짜/통화/주당 기준 오류를 포함.
- `RUFF_CACHE_DIR=/tmp/ruff-official backend/.venv/bin/ruff check backend/jusik/research_official_dividend_input.py backend/tests/test_research_official_dividend_input.py` — 통과.
- `MYPY_CACHE_DIR=/tmp/mypy-official PYTHONPATH=backend backend/.venv/bin/mypy --strict backend/jusik/research_official_dividend_input.py` — 통과.
- 기존 overlay focused 회귀 포함 29건 통과(API/endpoint 1건은 의도적으로 제외). 실제 MSFT 12건 사본에서 parser 원문 연결을 포함한 실행 통과. 최종 artifact SHA는 최종 커밋 기준 재확인 필요.

## 안전·운영 상태

- 별도 워크트리에서 코드·문서만 변경. 운영 DB, PAPER·실주문, 서비스, 배포, 원격 push는 변경하지 않았다.

## 증거와 재개

- supervisor 제공 DB 사본과 manifest: `/tmp/official-dividend-msft/`. 이 경로는 임시 검증 자료이며 저장소에 포함하지 않는다.
- 다음 시작: 아래 동결 입력과 회계 대사를 재사용해 환율·거래비용을 포함한 전체 평가액 검증으로 이어간다.
- workflow 판단: 도움 됨 — 기존 모델·검토/수집 DB 계약을 재사용했다.
- 근거: synthetic focused 24건 통과; 시간·비용 절감은 미측정.
- 다음 조정: 유지 — 새 원장이나 서비스 연결 없이 동결 입력 경계만 검증한다.

## 통합 결과와 후속 계산 검증

- 독립 검토가 수집 원문과 사건 ID 연결 누락 P2를 재현했다. 원 구현자가 attempt 원문 SHA·성공 상태·종목과 원문 재정규화, 사건/수정 ID·날짜 불변식 검사를 보완했다. 재검토 PASS, 원문/provider_key/vendor_date 변조 재현 모두 거부.
- main: 신규 입력·기존 review·overlay 세 파일의 `pytest -k 'not api'` 37 passed/2 deselected, Ruff와 strict mypy 통과. 변경 없는 API lifespan·프런트 빌드는 반복하지 않았다. 역할별 라우팅 사후 검사 4건 PASS.
- Microsoft FAQ·뉴스 원문 요청은 각 1회 HTTP403. 대체 [SEC 8-K](https://www.sec.gov/Archives/edgar/data/789019/000119312526224155/d125909d8k.htm)의 표지에서 Common stock/MSFT/NASDAQ을 읽고 원문 29,154 bytes를 신원 증거로 보존했다. 이전 배당 XLSX·12개 검토와 등록 revision 1의 DB 사본을 재사용했다.
- MSFT 실제 12건 동결 artifact SHA `438bf7e006c6ba6b8bd65bd75ef1452dd3050939f7f4bc25baa3c3ddc6371a3c`. main 재실행에서 같은 bytes를 재사용했다. 검토 이전 `58c024...` artifact는 감사용으로만 보존하며 최종 입력이 아니다.
- 다음 단계의 최소 독립 회계 대사도 수행했다. 동결된 2023-11-15 배당 주당 USD 0.75를 읽고 **가상** 보유량 137주·가격/현금으로 손계산한 기대값을 기존 순수 회계 함수와 대조했다. 수취배당 102.75, 배당락만큼 가격이 하락한 fixture에서 NAV 보존, 배당락 후 37주 매도 뒤에도 기존 수취권 유지, 지급 시 미수금→현금 이동, 중복 지급 재생 시 추가 현금 없음이 모두 통과했다.
- 매도 후 현금과 수수료는 독립적으로 지정한 fixture 상태다. 매매 엔진·환율·세금·실제 거래 달력·전체 비용 차감 NAV를 검증한 결과가 아니며 전략 실험·OOS 소비·성과 공개를 수행하지 않았다. 동결 artifact의 `nav_ready=false`와 기존 eligible 13/111 경계는 유지한다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261003-official-dividend-input/`; `verification-summary.json`, `routing-post.json`, `nav_oracle.py`, `nav-oracle-result.json`, `frozen/`, 원문 및 DB 사본. manifest SHA `6a77a417cffdc7b0a68296478534990208849ea5f56a2472a08d2ce8647a2c8a`.
- 관리형 worktree `/home/kwl/.codex/worktrees/official-dividend-input/jusik`는 clean이며 실행 프로세스·미병합 변경 없음. 후속 NAV/FX 검증에서 재사용할 free checkout으로 보존한다. 새 작업 소유자 배정 전 main 기준·브랜치를 준비한다. 사용자 루트 HANDOFF 보존.
