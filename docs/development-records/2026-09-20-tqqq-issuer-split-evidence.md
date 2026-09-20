# TQQQ issuer split evidence candidate

- 상태: 단일 issuer evidence candidate 확보·R1-04 승격 보류
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `tqqq-issuer-split-evidence-20260920`
- 범위: ProShares 공식 release와 기존 Alpha split 원문을 bounded offline 대조했습니다.
  자동 원장·성과·readiness에는 연결하지 않았습니다.

## 대조 결과

- symbol: `TQQQ`
- effective date: `2025-11-20`
- ratio: `2:1` (`split_factor=2.0000`)
- issuer semantics: 2025-11-20 market open 전 effective, 당일부터 post-split price 거래
- source: [ProShares ETF share splits release](https://www.proshares.com/press-releases/proshares-announces-etf-share-splits5)
- raw SHA-256: `a1d38b622c175942eade92db3e1b65cdd6014e3021c0ac83e89be304d6ba3748`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-tqqq-issuer-split-evidence/`

Issuer release의 날짜·비율이 Alpha 원문과 일치하는 것을 확인했습니다. 이는 단일
split의 issuer source 후보이지, 전체 ETF universe·가격 조정·보유수량·세금·fill 경계를
증명하지 않습니다.

## 판정

- `operator_verified=false`, `automatic_ledger_application=false`로 보존했습니다.
- R1-04/R1-05 checkbox, action review manifest, ledger, 성과, readiness는 변경하지 않았습니다.
- split 전후 가격·수량 보존은 별도 raw 가격과 position receipt가 필요합니다.

## 검증과 안전

- ProShares bounded GET 1회, raw SHA·크기 검증, Alpha exact match를 통과했습니다.
- 실제 주문, PAPER/live, runner 재개, 원격 push, Windows 종료는 없습니다.
