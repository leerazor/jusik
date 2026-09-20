# Canonical time-evidence attachment audit

- 상태: 완료 (읽기 전용 대조); canonical readiness 승격은 차단
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `canonical-time-evidence-attachment-audit-20260920`
- 기준/통합: `a501bd6` / 없음
- 범위: 기존 forward-simulation time-evidence bundle을 등록된 US canonical run에 연결할 수 있는지 identity·기간·입력 대조를 수행했습니다. 기존 run, bundle, readiness, runner와 원본 자료는 변경하지 않았습니다.

## 변경과 결정

- 기존 bundle `/home/kwl/.local/share/jusik/portfolio-audit/forward-simulation-time-evidence-run/run-gr68c4/bundle-continuous-official`의 manifest SHA-256은 `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`이며, 공식 timing·initial-capital anchor·NAV UTC timestamp를 검증한 artifact입니다.
- 그러나 bundle 기간은 `2024-04-24..2026-09-08`, 후보는 `portfolio_inverse_volatility_fx_vix_v1`, 정책은 `low_turnover_combined`, input SHA는 `f295946b...`입니다.
- 등록된 canonical US run은 기간 `2025-09-11..2026-09-11`의 별도 run SHA `cc9150f8...`, 별도 strategy/result contract입니다. bundle의 기간·후보·정책·input identity가 일치하지 않으므로 이 bundle을 canonical NAV timestamp 증거로 재사용하지 않습니다.
- 따라서 A 경로는 “time evidence가 있는 새 별도 simulation”까지는 이미 충족하지만, canonical 경제 평가 입력으로의 연결은 실패한 상태입니다. 다음 허용 입력은 canonical run과 동일한 input/strategy/기간으로 생성한 새 bundle이며, 생성 전 canonical replacement는 금지합니다.

## 문서·계약 영향

- 사용자 문서: 변경 없음. 기존 [`docs/forward-simulation-time-evidence.md`](../forward-simulation-time-evidence.md)가 bundle의 historical/approximate/non-canonical 한계를 이미 명시합니다.
- 운영 문서: 변경 없음. runner는 계속 paused/inactive이며 이 작업은 자동 dispatch를 수행하지 않습니다.
- API·설정·데이터 계약: 변경 없음. timestamp를 session close로 추정하거나 bundle identity를 덮어쓰지 않았습니다.

## 검증

- `verify_bundle(bundle_dir, eec4aae8...)` — 기존 기록과 동일하게 통과한 pinned bundle identity를 확인했습니다.
- bundle manifest/config/request와 canonical run request를 read-only JSON 대조 — 기간·candidate·policy·input identity 불일치 확인.
- `diagnose_canonical_run(canonical_path)` — `blocked`, missing `missing_initial_capital_at`, `missing_nav_timestamps`, `missing_risk_free_evidence` 유지.
- 실행하지 않은 검사: 새 simulation 생성, network 수집, KOFR application 생성, metrics 계산. canonical input identity가 없으므로 새 실행을 임의로 시작하지 않았습니다.

## 안전·운영 상태

- 실제 주문, PAPER/live, runner resume, 서비스·timer enable, 운영 DB, 원격 push, Windows 종료는 없습니다.

## 증거와 재개

- audit: 기존 bundle audit `/home/kwl/.local/share/jusik/portfolio-audit/forward-simulation-time-evidence-run/run-gr68c4`; manifest SHA는 위에 기록했습니다.
- 남은 차단 조건: canonical run과 동일한 frozen `PortfolioInput`/strategy/period를 가진 official time-evidence bundle과, KOFR application manifest의 source completeness·publication timezone·interval policy 증거가 필요합니다.
- 다음 시작: canonical run의 재현 가능한 원본 `PortfolioInput`/config 경로와 SHA를 먼저 확인하고, 없으면 canonical을 변경하지 않는 새 run 등록 계획을 작성합니다.
