# R2-04 independent drawdown chronology preflight

- 상태: 기술 preflight 완료·경제 승격 차단
- 기록 시각: 2026-09-20T01:50:00Z
- 작업 slug: `r2-04-drawdown-chronology-preflight-20260920`
- 기준/통합: `50199eb` / 코드 통합 없음
- 범위: frozen approximate US pilot의 저장 NAV·거래·dataset만 읽어 독립 Decimal chronology를
  실행했습니다. 전략·engine 재실행, canonical artifact 수정, 성과 evaluator 연결은 하지 않았습니다.

## 변경과 결정

- `backend/jusik/drawdown_chronology.py`의 독립 검산 CLI를 실제 frozen pilot에 적용했습니다.
- 초기자본 포함 peak NAV는 `112471016.1623047711480589801 KRW`, 독립 MDD는
  `26.463097776467786073068180512064383841960...%`로 계산됐고, `2026-02-12`에 20% latch가
  발생했습니다.
- latch 당시 보유한 5개 심볼은 모두 다음 available open인 `2026-02-13`에 전량 매도 관찰됐습니다.
- 독립 chronology 자체는 `success`이나, 저장 결과에는 latch 날짜·release chronology가 없어
  `stored_match=false`입니다. calendar·benchmark·future observation evidence도 unavailable입니다.
- 따라서 `MDD <= 20%` hard filter는 실패하며 R2-04/R4 후보 승격·경제 acceptance를 변경하지 않습니다.

## 문서·계약 영향

- 사용자·API·설정·운영 문서는 변경하지 않았습니다.
- 작업 등록부만 갱신했고, 결과는 외부 audit JSON으로 보존했습니다.

## 검증

- `PYTHONPATH=backend backend/.venv/bin/python -m jusik.drawdown_chronology --pilot ... --dataset ... --output ...` — exit 0
- report status `blocked`, chronology status `success`, MDD `26.463097776467786...`, latch `2026-02-12`
- audit report SHA-256: `ae439ad63585ea075211a1c10e7b0cb527d3da741daf59197f438ccc31248d39`
- 기존 drawdown chronology focused tests는 기존 구현 검증으로 보존되며, 이번 preflight는 추가 코드 변경이 없어 재실행하지 않았습니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·runner 재개·원격 push 없음.
- frozen input과 canonical artifact는 읽기 전용으로 사용했습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r2-04-drawdown-chronology/report.json`
- 남은 조건: MDD hard filter 초과와 stored latch chronology 부재 때문에 후보 승격은 차단됩니다.
- 다음 시작: 이 결과를 후보 비교의 negative outcome으로 사용하고, R1/R2 자료 completeness와 KOFR
  application evidence가 해결되기 전에는 경제 성과 계산을 승격하지 않습니다.
