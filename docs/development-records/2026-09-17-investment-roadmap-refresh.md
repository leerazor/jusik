# 투자 개발 로드맵 갱신

- 상태: 완료
- 기록 시각: 2026-09-17T03:09:16Z
- 작업 slug: `investment-roadmap-refresh`
- 기준/구현/통합: `995797a3faf0bd9a44321a93db2de3991d1d1144` / `fbf2ebd1a59b5073f13ea574c7d8d355a28194cd` / `206d091`
- 범위: canonical 실행 로드맵, 연구 운용 조건·backend reference 연결, 이 작업의 영구 기록만 갱신했습니다. 체크리스트 ID·체크 상태·완료 증거·의존성과 실행 JSON, 코드·설정·서비스·PAPER/live·주문은 보존했습니다.

## 변경과 결정

- 로드맵을 `일시 중지 — 운영자 보류`로 표시하고 balanced objective, 비용 차감 primary metrics, diagnostic metrics, `MDD <= 20%` hard filter, 무료 자료 우선·audit 후 최소 수집, 후보 최대 3개와 자동 선택 금지, bounded IS/validation/walk-forward/final untouched OOS/stress/PAPER/live 분리 순서를 명시했습니다.
- R7 진입은 최종 untouched OOS pass와 필요한 자료 게이트 뒤로 두고, 내부 순서를 격리·simulation/stress·prospective/stress 독립 review로 고정했습니다. 단계 실패는 PAPER를 차단합니다.
- 연구 운용 조건은 기존 JSON의 historical/current execution scope와 새 canonical 설계를 분리하고, 신규 dispatch 전 JSON/SHA 동기화를 요구하도록 명확히 했습니다. 연구 backend 문서는 canonical 링크와 적용 범위만 추가했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/investment-development-roadmap.md` — 실행 순서와 승인 게이트를 갱신했습니다.
- 운영 문서: `docs/research-mandate.md`, `docs/research.md` — JSON 동기화 게이트와 정본 범위를 명시했습니다.
- API·설정·데이터 계약: 해당 없음. `docs/research-mandate.json`과 기존 PAPER10% contract는 변경하지 않았습니다.

## 검증

- `git diff --check` — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_development_runner_roadmap.py` — 16 passed.
- `PYTHONPATH=backend backend/.venv/bin/python`의 `load_roadmap` — 40개 항목 로드, pre/post ID·체크 상태 40개 일치.
- `PYTHONPATH=backend backend/.venv/bin/python -m jusik.development_runner status --config /home/kwl/.config/jusik/roadmap-development-runner.json` — `paused=true`; `jusik-development-runner.service` `inactive`; timer `inactive`·`disabled` 확인.
- Markdown 로컬 링크 검증 — 변경 파일 4개에서 8개 검사, 누락 0개.
- 변경 파일 allowlist — 정확히 허용된 네 경로만 변경.
- 실행하지 않은 검사: backend/frontend 코드 검사와 연구 실행은 문서 작업 범위 밖이며, live/PAPER 주문은 실행하지 않았습니다.

## 안전·운영 상태

- 실제 주문, PAPER/live 상태, 운영 DB, 서비스, 외부 수집, 배포와 remote push를 변경하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 실행 JSON의 기존 문서 SHA만 보존.
- 남은 작업·차단 조건: 문서 통합은 완료했습니다. 운영자가 승인 설계를 JSON에 반영하고 SHA를 동기화하며 dispatcher fail-closed 구현·검증을 별도 완료하기 전까지 service/timer enable·resume 및 신규 research dispatch를 금지합니다. 최종 untouched OOS go/no-go 실패도 stress/PAPER 차단 조건입니다.
- 다음 시작: JSON과 문서 SHA를 대조한 뒤 로드맵 parser·문서 링크·체크리스트 보존 검사를 다시 실행합니다.
