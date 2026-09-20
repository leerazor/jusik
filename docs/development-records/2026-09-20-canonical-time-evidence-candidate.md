# Canonical time-evidence candidate replay

- 상태: 완료 (candidate audit); canonical 승격 보류
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `canonical-time-evidence-candidate-20260920`
- 기준/통합: `68538e9` / 미통합
- 범위: R0 frozen manifest를 deterministic replay하고, 새 결과에 공식 NMS session timing을 연결한 candidate artifact를 audit했습니다. 기존 canonical run과 frozen artifact는 변경하지 않았습니다.

## 변경과 결정

- replay output은 `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/replay.json`에 보존했습니다. replay catalogue SHA-256은 `07f744267c2c2c3a883bc5b496ef75c4de377f3079db21e0d460f897cf60d385`이고, `comparison.all=true`, dependency dirty=false입니다.
- `attach_time_evidence()`로 공식 NMS calendar를 연결해 252개 NAV를 `2025-09-11T20:00:00Z`부터 `2026-09-11T20:00:00Z`까지 기록하고, initial-capital anchor를 `2025-09-11T13:30:00Z`로 기록했습니다.
- enriched result SHA-256은 `63c45f0d727b409d692c5483af7922e120ebc0a6ecfcb9a0a4497228a6bd57b7`입니다. candidate run bytes SHA-256은 `5e4613e2fedad5ecb99f6308686b4e6151df52ba5356d7095dac266a2f4663a3`입니다.
- candidate `diagnose_run()` 결과는 `blocked`/`ready_for_metrics=false`이며 시간 두 code는 제거되고 다음만 남았습니다: `missing_session_completeness_evidence`, `missing_calendar_evidence`, `missing_cost_inclusion_evidence`, `missing_risk_free_evidence`, `missing_calculation_policy`.
- 이 결과는 timestamp 생산 경계가 동작함을 증명하지만, replay 결과를 기존 canonical run으로 교체하거나 historical timestamp를 원본 사실로 소급하는 근거는 아닙니다. canonical 승격에는 새 run identity·manifest chain·동일 조건 review가 필요합니다.

## 문서·계약 영향

- 사용자 문서: 기존 canonical/approximate 분리 규칙을 유지하므로 별도 계약 변경 없음.
- 운영 문서: runner paused/inactive, service/timer 상태, PAPER/live와 주문 경로는 변경하지 않음.
- API·데이터 계약: candidate만 audit root에 생성했습니다. tracked canonical artifact·readiness constants·remote는 변경하지 않았습니다.

## 검증

- `python -m jusik.market_research_replay ...` — deterministic replay exit 0, `comparison.all=true`, 252 NAV/106 trades legacy 비교 통과.
- `attach_time_evidence` + `diagnose_run(candidate)` — timestamp/anchor 유효, 시간 missing code 2개 제거, KOFR 및 기타 evidence는 fail-closed 유지.
- 기존 focused pytest 85개, Ruff, 변경 source strict mypy — 통과.

## 안전·운영 상태

- 새 artifact 생성 외에 기존 DB·run·서비스·runner·PAPER/live·원격 push·Windows 상태를 변경하지 않았습니다.

## 증거와 재개

- audit root: `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/`.
- 남은 조건: candidate를 canonical로 채택하려면 별도 등록된 run/manifest와 session evidence를 만들고, KOFR application evidence를 완성해야 합니다. 기존 canonical 교체는 자동 수행하지 않습니다.
- 다음 시작: KOFR application contract를 현재 245행 source evidence와 canonical 252 NAV 날짜에 대해 fail-closed로 생성할 수 있는지 조사합니다.
