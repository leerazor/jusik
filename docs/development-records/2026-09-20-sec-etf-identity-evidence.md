# SEC ETF identity evidence candidate

- 상태: SOXL/TQQQ identity candidate 확보·R1-05 승격 보류
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `sec-etf-identity-evidence-20260920`
- 범위: SEC 공식 filing index에서 기존 unresolved symbol의 CIK·정식 명칭을 확인하고 raw와 SHA를 보존했습니다. 기존 ticker-map parser와 catalog는 변경하지 않았습니다.

별도 `research_sec_etf_identity.py` parser도 추가했습니다. SEC index raw 하나에
symbol·title·CIK가 모두 존재하고 accession/HTTPS provenance가 유효할 때만 identity
candidate를 반환하며, 누락·credential URL·비정상 입력은 fail-closed 합니다. 기존
catalog에는 자동 병합하지 않습니다.
candidate 여러 건을 결합하는 CIK↔symbol mapping도 추가해 동일 CIK의 다른 symbol이나
동일 symbol의 다른 CIK 충돌을 거부합니다. 보존 raw 2건의 실제 mapping은
`{"0001174610": "TQQQ", "0001424958": "SOXL"}`로 재현했습니다.

## 결과

- `SOXL` → `0001424958`, `Direxion Daily Semiconductor Bull 3X Shares`
- `TQQQ` → `0001174610`, `ProShares UltraPro QQQ`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-etf-identity-evidence/`
- request manifest가 accession, source URL, raw bytes, SHA-256을 고정합니다.
- 새 parser로 보존 raw를 offline replay해 `SOXL`·`TQQQ` 2/2 identity를 재현했습니다.

현재 SEC `company_tickers.json`의 unresolved 결과를 사후에 조용히 덮어쓰지 않고,
ETF series/class identity를 별도 evidence source로 분리했습니다. 이 자료는 identity
후보를 보완할 뿐이며, 해당 CIK의 target-period filing coverage, PIT availability,
상장폐지·중단일·split/dividend 권리 경계를 증명하지 않습니다.

## 판정

- 기존 catalog `coverage=incomplete`와 `unresolved_symbols` 보존을 유지합니다.
- R1-05 checkbox, action review, 원장, 성과, readiness는 변경하지 않습니다.
- 다음 구현 후보는 별도 SEC ETF identity adapter와 source-specific coverage report이며,
  기존 ticker map과 섞지 않고 conflict/series/class ambiguity를 fail-closed로 검증해야 합니다.

## 검증과 안전

- SEC 공식 index bounded GET 2회, raw SHA·크기·symbol/CIK 문자열 대조를 통과했습니다.
- identity parser focused pytest 5개, Ruff check/format, strict mypy를 통과했습니다.
- mapping 충돌 경계 포함 focused pytest 8개와 실제 raw mapping replay를 통과했습니다.
- 실제 주문, PAPER/live, runner 재개, 원격 push, Windows 종료는 없습니다.

## CIK submissions inventory

확인된 CIK로 SEC submissions를 각 1회 조회해 target-period inventory를 만들었습니다.

- SOXL: 전체 1,023건, target period 771건
- TQQQ: 전체 1,066건, target period 1,063건
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-etf-submissions/`

두 결과는 ETF filing inventory일 뿐 corporate-action coverage나 PIT 증거가 아닙니다.
제출 유형이 광범위하고 series/class별 문서가 섞이므로, 이를 기업행사로 해석하거나
catalog coverage를 승격하지 않습니다.

초기 sidecar의 TQQQ SHA 오타를 발견해 실제 raw bytes SHA로 교정했고, 이후 두 파일의
크기·SHA 검증을 다시 통과했습니다.

`research_sec_etf_coverage.py`의 inventory-only report로 두 submissions를 재생성해
SOXL 771건·TQQQ 1,063건과 form 분포를 확인했습니다. report는 source/identity SHA를
함께 pin하지만 completeness·PIT·기업행사 의미를 주장하지 않습니다.
