# R2-04 독립 DD chronology

- 상태: 차단 (기술 slice 구현 완료, 필수 증거 부족)
- Task/attempt: `roadmap-r2-04-v1` / `cb6b03f16c8f438cb4c55cfc551fe089`
- 조사 기준 main: `80cf90abb3fc01006c5ec758bc652e3e8089f967`; worktree 기준 `7d913183a8c04312a33b910319976a828795398e`.
- 구현 최종: `a74bf7ebc41d15ccbadadc91cf5375603f696008`; Astra local main 통합: `274a48c22175287280c4113c9351de3f3b9d9c38`.

## 확인과 결정

R0 완료 체크와 근거 문서를 확인했습니다. 동결 manifest에 연결된 자료 4개의 SHA-256은 모두 일치하며 저장 미국 파일럿은 approximate 252세션입니다. 현재 mandate JSON과 전략 파일의 해시도 기록했습니다. prompt에는 첨부 roadmap hash 값이 없어 현재 로드맵 해시만 보존했습니다.

전략 코드를 호출하지 않는 `drawdown_chronology` stdlib 모듈을 추가했습니다. Decimal precision 50에서 초기 자본 포함 peak/DD/MDD와 정확한 20% latch를 계산하고, signal/fill chronology·전체 수량 ledger·latch 이후 buy 금지·종목별 다음 유효 open 전량 청산을 검증합니다. 12개 고정 offline fixture와 별도 문서를 추가했습니다. 원래 approximate grade는 보존했습니다.

저장 미국 파일럿 252세션·106거래를 동결 bars와 대조한 결과 MDD·세션별 DD·최종 latch boolean이 `1e-20` percentage-point tolerance 안에서 일치했고 latch 시점 5개 보유 종목의 첫 유효 open 전량 청산을 관측했습니다. 저장 파일럿에는 최초 latch 날짜와 실행 중 release chronology가 없어 전체 chronology match는 주장하지 않습니다. 이는 저장 NAV 기반 chronology 진단이며 전체 NAV 회계 증명은 아닙니다.

## 차단과 검증

이 시도에서 별도 검증된 거래소 calendar, 동일 조건 benchmark, prospective future observation 증거는 없습니다. 저장 파일럿의 readiness capability flag만으로 이 증거를 만들지 않았으며 최종 진단은 `blocked`입니다. 입력 자료와 원래 결과의 approximate 등급은 변경하지 않았습니다.

- 입력 hash 검사: 4개 일치.
- 이전 시도(`665ad529`)의 roleless routing preflight는 실패했으나, 이번 adapter 재시도(`cb6b03f16c8f438cb4c55cfc551fe089`)는 PASS로 구현 worktree가 생성되었습니다.
- `PYTHONPATH=. .venv-verify/bin/python -m pytest tests/test_drawdown_chronology.py -q` from `backend/` — PASS, 6 tests.
- `.venv-verify/bin/ruff check jusik/drawdown_chronology.py tests/test_drawdown_chronology.py` from `backend/` — PASS.
- `.venv-verify/bin/ruff format --check jusik/drawdown_chronology.py tests/test_drawdown_chronology.py` from `backend/` — PASS.
- `.venv-verify/bin/python -m mypy --strict jusik/drawdown_chronology.py tests/test_drawdown_chronology.py` from `backend/` — PASS.
- 저장 파일럿 CLI 진단 — `blocked`; stored DD/MDD·세션별 DD·최종 latch boolean match, 전체 `stored_match=false`, 최초 latch 날짜/release chronology unavailable, 5/5 liquidation `observed`, calendar/benchmark/future evidence `unavailable`.
- round2 exact commands/logs: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-04-cb6b03f1/verification-round2.txt` (task interpreter `backend/.venv-verify/bin/python`, package versions pytest 9.1.1 / mypy 1.20.2 / Ruff 0.16.6).
- Terra 독립 검토: 1차 지적 수정 및 최종 PASS. 최종 pytest6·Ruff check/format·strict mypy와 main 통합 검사도 PASS입니다.
- main에서 같은 저장 파일럿 CLI 결과를 다시 생성해 worktree 결과와 byte 일치를 확인했습니다. 원본 및 보존 입력8개 SHA, 전략/shared model/R1 collector/roadmap/root HANDOFF 무변경 확인도 PASS입니다.
- 전체 backend suite는 신규 전략 실행 금지 및 독립 모듈 범위를 지키기 위해 실행하지 않았습니다. frontend 변경이 없어 frontend 검사는 해당 없습니다.
- 1차 검증에서 추가 inline fixture가 실행되어 고정 fixture 한도 증명이 실패했습니다. 검토에서 발견 후 최종 테스트를 기존12개 fixture에서 파생하도록 수정했습니다. 이 초기 일탈은 `REVIEW-2.md`에 보존합니다.
- 격리 환경 준비 중 offline cache 부족과 작업 디렉터리 경로 오류가 있었습니다. 기존 설치 도구를 별도 `.venv-verify`로 복사한 뒤 정확한 cwd에서 재검증했습니다. 최종 명령/로그는 `verification-round3.txt`, main 근거는 `integration-verification.json`입니다.

## 영향과 재개

변경은 독립 검산 모듈·fixture·검사·설명 문서와 이 개발 기록입니다. R2-04 체크는 필수 증거 부족으로 미완료로 유지합니다. 네트워크·GPU·신규 pilot/backtest·PAPER/live·운영 원장·서비스·설정·원격 push는 수행하지 않았습니다. 실제 주문과 broker API 호출은 없습니다.

Audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-04-cb6b03f1`. 입력 manifest는 `input-verification.json`, 실행 결과는 `drawdown-chronology-pilot.json`, round2 명령·로그는 `verification-round2.txt`에 보존했습니다. 파일럿 CLI는 동결 dataset bars를 읽었고 새 자료를 수집하거나 실행을 생성하지 않았습니다.

관측된 최초 latch는 2026-02-12, 보유5종목의 청산은 2026-02-13입니다. 원본 결과에는 보유 bar 결측이 없어 결측 이후 전략 pending 의도의 실제 지속성을 이 파일럿으로 증명할 수 없습니다. 독립 fixture가 기대 chronology를 검증하지만 전략 수정·실행 증명은 별도 판단으로 남깁니다.

사용자 설명 문서는 `docs/drawdown-chronology.md`에 갱신했습니다. API/설정/운영 계약과 UI 변경은 없습니다. 기존 파일럿 진단이며 새 성과 비교가 아니므로 웹 성과 catalog 공개는 해당 없습니다. 원본 approximate 등급을 승격하지 않습니다.

이 slice는 기술 산출물 통합·검사까지 마쳤지만 필수 증거 부족으로 task는 blocked이며 R2-04 checkbox는 변경하지 않습니다. 재개 시 audit/HANDOFF.md와 최종 보고서를 먼저 읽고 독립 달력·벤치마크·미래 관찰·저장 latch 시점/해제 이력의 확보 가능성을 판단해야 합니다. 신규 연구나 전략 변경은 이번 범위에서 수행하지 않습니다.

증거64파일의 SHA와 handoff를 durable audit에 보존·검증한 뒤 이번 merged worktree와 branch만 정리했습니다. 기존 root HANDOFF.md와 다른 worktree는 보존합니다.

## 2026-09-23 재검증 (attempt `9d4a546c`)

- 기존 독립 Decimal 구현과 고정 fixture 12개를 소유 worktree에서 재검증했습니다. Python 3.13.15 환경에서 focused pytest 6개, Ruff check/format, strict mypy가 모두 통과했고 독립 review도 PASS(P1/P2 없음)입니다.
- frozen pilot 및 dataset SHA가 2026-09-16 `input-verification.json`과 일치했습니다. 저장 파일럿 CLI 결과는 기존 보고서와 동일합니다: 계산 MDD `26.463097...%`, latch `2026-02-12`, 5개 보유 종목이 다음 available open인 `2026-02-13`에 청산 관측. 저장 latch date/release chronology와 calendar/benchmark/future evidence는 없습니다.
- MDD가 20% hard filter를 초과하고 필수 chronology·시장 근거가 없어 R2-04는 미체크 상태로 유지합니다. 경제 acceptance를 완료하거나 approximate 등급을 승격하지 않습니다.
- 이번 재검증에서 전략, R1, PAPER/live, 운영 원장, 서비스, 설정, remote, GPU, network 및 시장 입력은 변경하지 않았습니다.
- 새 pilot 결과: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-r2-04-9d4a546c/drawdown-chronology-pilot.json`, SHA-256 `ae439ad63585ea075211a1c10e7b0cb527d3da741daf59197f438ccc31248d39`.
- 검증 요약: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-r2-04-9d4a546c/verification-summary.json`, SHA-256 `1aa7801af2237a3004a65c61f0492df442a7b3ee74654088ca4d658adf0b8385e`.
