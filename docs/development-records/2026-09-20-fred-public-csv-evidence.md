# FRED 공개 CSV FX 근거 수집

- 상태: 완료된 자료 조사 slice; 경제 성과 적용은 차단
- 기록 시각: 2026-09-19T23:17:03Z
- 작업 slug: `fred-public-csv-evidence-20260920`
- 기준/통합: `376f050` / `e7245de`
- 범위: FRED 공개 graph CSV의 DEXKOUS bounded raw evidence를 저장하고 요청·SHA
  메타데이터를 기록했습니다. collector 설정·성과 계산·readiness·원장에는 연결하지
  않았습니다.

## 변경과 결정

- FRED API key 없이 공식 공개 CSV endpoint를 사용해 `2025-09-11`~`2026-09-11`을
  한 번 조회했습니다(HTTP 200, header 포함 263행).
- 원문은 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-csv-evidence/`
  아래에 보존했고, raw SHA-256은
  `06751750c69089e33aaac8d5bdd0e102887c9c4db2d4d5da529561ad318f8210`입니다.
- 공개 CSV의 관측값과 retrieval 시각만 확보했으며 당시 provider availability/PIT
  timestamp, 결측일 의미, source-to-NAV 적용 시각은 증명하지 않습니다. 따라서
  `FRED_API_KEY` 누락을 readiness에서 제거하거나 FX/NAV를 재계산하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. source evidence만 추가했고 제품 결과를 바꾸지 않았습니다.
- 운영 문서: 해당 없음. 서비스·runner 설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 변경 없음. 기존 authenticated FRED collector 계약은 유지합니다.

## 검증

- `curl` bounded request — HTTP 200, 4,926 bytes
- `sha256sum` 및 line-count — raw 263 lines, SHA above
- 실행하지 않은 검사: collector/readiness/performance integration — 공개 CSV는 기존 JSON
  cache/API 계약과 동일하다고 입증되지 않았고 자동 적용하지 않았습니다.

## 안전·운영 상태

- read-only public network fetch만 수행했습니다. 원장·서비스·PAPER/live·주문·원격
  push·Windows 종료는 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-csv-evidence/`;
  manifest: `request.json`; raw SHA는 위에 고정했습니다.
- 남은 작업·차단 조건: CSV parser/source contract와 FRED JSON contract의 동등성,
  PIT availability, NAV 적용·calendar completeness를 별도 검증해야 합니다.
- 다음 시작: 공개 CSV를 자동 성과 입력으로 연결하지 말고, 필요하면 별도 read-only
  parser/fixture 계약을 설계한 뒤 source/application evidence를 독립 검토합니다.
