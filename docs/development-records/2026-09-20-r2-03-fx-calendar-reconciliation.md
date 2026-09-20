# R2-03 FX/calendar reconciliation

- 기록 시각: 2026-09-20T02:55:00Z
- 원본은 기존 frozen artifact와 기존 ALFRED sampled-vintage 산출물이며 모두 read-only로 읽었습니다.
- canonical US equity sessions: `252` (`2025-09-11`~`2026-09-11`)
- sampled ALFRED FX dates: `251`; source summary의 nonblank coverage는 `251/251`이지만 이는 FX
  관측일 coverage이지 canonical portfolio session coverage가 아닙니다.

## 날짜 대사

- canonical session에 없는 FX 날짜: `2025-10-13`, `2025-11-11`
- FX sampled date 중 canonical session에 없는 날짜: `2026-04-03`
- exact date intersection: `250/252`

## 판정

- 주간 ALFRED first-seen 값은 exact publication instant가 아니라 upper-bound observation입니다.
- FX 관측일과 XNYS portfolio session의 불일치를 carry-forward·삭제·추정으로 메우지 않았습니다.
- 따라서 R2-03의 환율 시점·달력·반올림 계약과 USD/KRW NAV 경제 acceptance는 blocked/not-evaluated입니다.
  향후에는 동일한 calendar/application policy와 PIT-valid FX receipt가 먼저 고정되어야 합니다.
