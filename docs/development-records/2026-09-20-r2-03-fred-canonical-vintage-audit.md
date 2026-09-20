# R2-03 canonical FRED vintage audit

- 상태: canonical vintage evidence 완료·FX PIT application 차단
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r2-03-fred-canonical-vintage-audit-20260920`
- 기준/통합: `76d66f2` / 통합 예정
- 범위: FRED DEXKOUS를 canonical 2025-09-11~2026-09-11 범위와 realtime vintage 범위로 한 번 조회해 관측일 대비 availability를 계산했습니다. 기존 NAV·DB·원장은 변경하지 않았습니다.

## 변경과 결정

- 응답은 HTTP 200, 263개 날짜 행, numeric observation 252개였습니다.
- `realtime_start <= observation date`인 numeric 관측은 `0/252`였습니다. 모든 canonical FX 값은 관측일 이후에 realtime 범위에 나타났습니다.
- 따라서 FRED current vintage를 거래일 시점 FX로 사용하거나 canonical NAV/Sharpe에 연결하지 않습니다. FRED 원천이 존재한다는 사실만으로 PIT completeness를 주장하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 경제 readiness와 fail-closed 정책은 유지합니다.
- 운영 문서: `docs/worktree-tasks.md`에 canonical 결과를 등록합니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- bounded canonical FRED vintage request — HTTP 200, 263 rows, 252 numeric, availability on/before observation `0/252`.
- response SHA-256: `d8c76764dde9dacb50abb3ed0fa6bf5724b6e714edc991ceb96222dab28e8341`.
- summary SHA-256: `906e5e20176234a9464e3c08348c1d3543e9fe47c25d579f18c09470cb04e177`.

## 안전·운영 상태

- 실주문·PAPER/live 승격·remote push·Windows 종료를 수행하지 않았습니다.
- raw/summary는 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-vintage-canonical/`에만 저장했습니다.

## 증거와 재개

- 남은 작업·차단 조건: 거래일 이전 이용 가능 FX 원천 또는 명시적 대체 policy와 evidence가 필요합니다. 현재 FRED vintage만으로는 R2-03을 완료할 수 없습니다.
- 다음 시작: 승인된 FX 대체 원천을 조사하거나 SEC 기업행사 수동 review 경로를 진행합니다.
