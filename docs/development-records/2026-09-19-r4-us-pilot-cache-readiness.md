# R4 미국 pilot cache readiness 재검증

- 상태: 자료 게이트 차단·pilot 미실행
- 기록 시각: 2026-09-19T01:20:00+09:00
- 범위: 기존 US approximate pilot cache를 read-only `collect-status`로 확인했습니다. 네트워크 수집, 연구 실행, 결과 덮어쓰기, PAPER/live와 주문은 수행하지 않았습니다.

## 검증

- 명령: `PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_research_cli collect-status --cache /home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/us-pilot-1y-stable-cache --market US --start 2025-09-11 --end 2026-09-11 --output /tmp/jusik-collect-status.json`
- 결과: cache entries `84`, `completed=false`, `ready=false`, exit code `2`
- 누락 자격증명: `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`
- 기존 cache checkpoint와 원본 artifact는 변경하지 않았습니다.

## 2026-09-19 bounded 수집·pilot 시도

frozen cache 복사본에서 요청 예산 405, `--resume`로 bounded 수집을 실행했습니다. 수집은 exit 0으로 완료되었고 prepared dataset은 universe 20,574개, bars 20,306개, FX 272개, events 121개를 포함했습니다. 그러나 별도 임시 DB에서 approximate 1년 pilot을 실행한 결과는 `status=insufficient`, `completeness=incomplete`, `readiness.ready=false`였습니다. 결과에 표시된 불확실 기업행동 심볼 때문에 거래·equity·metrics를 만들지 않았습니다.

- pilot run: `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r4-us-pilot-collection-5e966f4/pilot-run.json` (SHA-256 `c93ea954610ca0cfb94aeb577b1ebd7a4b343651fdc638e296fca2c8e38d22b1`)
- prepared dataset: `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r4-us-pilot-collection-5e966f4/us-pilot-prepared.json` (SHA-256 `54d718e509028f1cdd93817e55af2bd56572a796f9e7376bc2c29f37b28312c2`)
- 결과 입력 hash: `5b15e14b847fa95b1326aa13e90e0863b86e249e487f515c7bfb295a8d2a6f3c`; data contract hash: `f5bf6e9342f0fc6e16dd5f2e950fc4e4963d349ef00af2f5fa7958c72914a9fd`

이 결과는 R4 자료 계약의 부족함을 구체화한 것이며 경제 성과나 후보 승격 근거가 아니다. 불확실한 기업행동 원문·관측시각이 보강되기 전에는 R4-02~R4-05, stress, PAPER를 진행하지 않는다.

수집 dataset의 `observed_at=null` 이벤트 36개 심볼을 canonical review DB와 read-only 대조했지만 overlap은 0개였습니다. 현재 review DB에서 검토된 심볼은 NVDA와 TQQQ뿐이므로, 기존 review를 다른 심볼에 전이하거나 관측시각을 추정하지 않았습니다.

## 판정과 재개 조건

기존 frozen US pilot은 independent cost/NAV 검증을 통과했지만, 현재 R4 pilot의 자료 readiness와 동일하지 않습니다. 따라서 기존 결과를 현재 policy의 새 pilot 또는 strict/PIT 근거로 재명명하지 않습니다. 누락 자격증명이 준비되거나 동일한 provenance를 가진 공급자 응답 파일이 제공되어 cache coverage·membership·FX·기업행동 계약을 다시 통과할 때만 bounded pilot을 실행합니다. 그 전에는 R4-01~R4-05와 경제 승격을 보류합니다.
