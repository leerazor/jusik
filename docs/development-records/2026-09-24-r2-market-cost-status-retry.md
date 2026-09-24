# R2-02 저장 비용 진단 상태 재검증

- 상태: 기술 slice 완료, R2-02 전체·경제 수용 대기
- 기록 시각: 2026-09-24T03:18:48Z
- 작업 slug: `r2-market-cost-status-retry`
- 기준: `be5782cced2b46fadf87ce8230c65934dbc68fd2`
- 범위: 독립 비용 진단, 오프라인 회귀, 한국어 계약만 수정했습니다. 전략·공유 모델·고정 세율·PAPER/live·운영 원장은 변경하지 않았습니다.

## 변경과 결정

- 저장 거래의 수수료 등 불일치는 최상위 `invalid`로 전파합니다. 합성 저장 pilot의 fee 불일치로 검증했습니다.
- 제공된 체결 시각의 현지 session 날짜와 UTC 순서를 확인합니다. `executed_at`과 `timestamp`가 함께 있으면 같은 시각이어야 합니다. 시각이 없는 동결 pilot에는 시각을 추정하지 않습니다.
- KR/KRW, US/USD에서 매수·매도 fee, 체결가에 포함된 slippage, 매도에만 부과한 모델 세율을 독립 Decimal 기대값으로 대조했습니다. `0.0018`은 동결 실행의 모델 가정이며 법정 세율이 아닙니다.
- 선택된 BanKIS online 공식 프로필과 source audit은 보존하되 동결 pilot에 소급 적용하지 않습니다. 시장 board·상품·계좌별 적용 범위와 법정 유효기간, 고객 청구 및 체결·결제 receipt가 없어 `statutory_validation=unavailable`입니다.

## 문서·계약 영향

- 한국어 계약: `docs/market-cost-diagnostics.md` 갱신.
- 로드맵 R2-02 checkbox는 전체 조건 미충족으로 유지. 경제 평가는 `not-evaluated`.
- 서비스·설정·원격 상태 변경 없음.

## 검증

- 입력 source audit SHA-256: `9ee18ab9d8e7fabef1a96accdc9ec0b566a2da5d64ed9101cf4519e5069e826d`.
- 동결 미국 pilot SHA-256: `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`.
- 소유 Python `3.13.15`, focused pytest 30 passed, Ruff check/format, 설정된 mypy 2파일, `git diff --check` 통과.
- 동결 pilot 1회 CPU 진단: 252세션·106거래, 산술 `success`, 저장값 일치, 최상위 `blocked`, 법정 `unavailable`, 경제 `not-evaluated`. 결과 SHA-256 `fedb18e50092521778279b446b9cf9c09d963f01343cbe86d2835ab38cbd77cb`.
- 네트워크·simulation/replay·GPU 실행 0회. 새 고정 시나리오 16개 이하, artifact 20 MiB 이하.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r2-02-5580d990/`.
- 전체 R2-02 재개 입력: 시장 board·상품·계좌 범위, 세목별 법정 유효기간, 거래일 기준, 실제 고객 비용 receipt와 체결·결제 시각. 해당 근거를 동결 실행과 구분해 별도 계약으로 검증해야 합니다.
