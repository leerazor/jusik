# R1 public-evidence catalog integrity audit

- 상태: 기술 재구축 완료·coverage incomplete 유지
- 기록 시각: 2026-09-20T02:10:00Z
- 작업 slug: `r1-public-evidence-catalog-integrity-audit-20260920`
- 기준/통합: `d38cfaf` / 코드 통합 없음
- 범위: 기존 v2 catalog를 읽기 전용으로 검사한 뒤, cached Alpha/SEC/Nasdaq raw를 현재
  fail-closed builder로 별도 catalog에 재구축했습니다. 기존 raw와 catalog, production code는
  변경하지 않았습니다.

## 변경과 결정

- 요청 universe 10개와 catalog item 1,597개를 대조했습니다.
- 27개 item이 요청 universe 밖 심볼(`ABL`, `AHG`, `BROG`, `DOGZ`, `ECDA`, `ELWS`,
  `LXEH`, `MCAF`, `MDIA`, `MPLN.W`, `MSGM`, `NCAC`, `NUBI`, `NVFY`, `PGTI`, `PNST`,
  `POL`, `PRSO`, `PTHRU`, `PYPD`, `RCAC`, `SYT`, `TENX`, `VIA`, `VIASP`, `VST.A`, `VSTE`)로
  남아 있었습니다.
- `SOXL`·`TQQQ`는 SEC identity candidate가 별도 확보됐지만 v2 catalog의 unresolved 상태는
  그대로였습니다. 이를 사후 수정하거나 R1-05 coverage로 승격하지 않았습니다.
- 새 catalog는 1,570개 item, out-of-universe 0, unresolved 0, `coverage=incomplete`입니다.
  Nasdaq raw의 비요청 halt 27개는 rejected 목록으로 manifest에 보존했습니다.
- SEC identity candidate `SOXL→0001424958`, `TQQQ→0001174610`을 새 mapping에 결속했습니다.
- 종목별 source coverage 보고서도 별도 artifact로 생성했습니다. report SHA는
  `f3faa820050e150978a3cc78d8792a0dbd17ec6ffb14e5f2f996c8cd85556d49`이며, SEC는 10/10 종목,
  Alpha는 7/10 종목, Nasdaq Trader는 0/10 종목이었습니다. AMD/ARM/COHR는 Alpha가 없고
  SOXL/TQQQ는 SEC evidence가 없습니다. 이는 source availability 확인일 뿐 provider 전체
  coverage·PIT·기업행사 권리 증명이 아닙니다.

## 문서·계약 영향

- 작업 등록부·개발 기록과 외부 audit/catalog artifact만 추가했습니다.
- R1-05 checkbox, coverage, PIT, 기업행사·성과·readiness는 변경하지 않았습니다.

## 검증

- requested-symbol membership audit — 기존 catalog 27개 out-of-universe, 2개 unresolved
- rebuilt catalog — 1,570 items, out-of-universe 0, unresolved 0, `coverage=incomplete`
- source catalog SHA: `0c7b6b568ef87e9c752204a8974434767ba0460ead76ac7b4cc3f15a8a2c31f3`
- report SHA: `c36ce6ffc982c8f8afa4b5da0d8e9dace6ab9a18ee93533b8f068dd8de0830e1`
- rebuilt catalog semantic SHA: `0ffb17730ad4fe98e808ff6f3973359f67aa6f2665b28dc53ca51fc7b638e03b`
- symbol coverage report: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-catalog-rebuilt-20260920/symbol-coverage.json`
- symbol coverage report SHA: `f3faa820050e150978a3cc78d8792a0dbd17ec6ffb14e5f2f996c8cd85556d49`

## 안전·운영 상태

- 네트워크 수집·실제 주문·PAPER/live 승격·runner 재개·remote push 없음.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r1-catalog-integrity-audit/report.json`
- 남은 조건: 새 catalog의 provider 전체 coverage/PIT와 corporate-action 권리·가격 경계는
  여전히 미증명이며 R1-05/경제 acceptance를 승격할 수 없습니다.
- 다음 시작: 새 catalog를 source-specific coverage 검증의 입력으로만 사용하고 자동 원장·성과
  적용은 계속 차단합니다.
