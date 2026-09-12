# 포트폴리오 노출·비용 절충 진단

이 진단은 `20260911T132132Z-worktree-development/unheld-entry-real32`에 고정된 32개 시뮬레이션을 읽어 실제 노출, 체결 회전율, 수수료·슬리피지·거래비용·FX 비용과 순손익을 정리한다. `results.json`, `preregistration.json`, 각 simulation 바이트와 핵심 소스 해시를 분석 시점에 재검증한다.

실제 결과는 기간 8개 × arm 2개(control/variant) × 비용 배수 2개(1x/2x)의 32행이다. 각 행의 일별 노출은 UTC로 변환한 equity 관측값에서 날짜별 마지막 관측값을 사용하며 보간하지 않는다. `daily.csv`와 `diagnostics.json`에 날짜별 값이 함께 남는다. 회전율은 매수·매도 execution notional의 절대값 합계(KRW)이고, 백만 원 기준이 아니라 고정 초기자본 100,000,000 KRW 대비 백분율도 계산한다.

각 기간·arm의 c2-c1 비교 16행은 실제 2x 체결과 실제 1x 체결의 차이다. 비용 배수가 바뀌면 현금과 체결 수량이 달라질 수 있으므로 이 비교는 고정 체결 산술 진단과 동일하지 않다. 비용 decomposition은 기존 entry attribution의 symbol 회계를 재사용하며 `fee + slippage = transaction_cost`, 거래별 비용 합계, FX 비용 합계와 최종자산−초기자산 순손익을 재조정한다.

별도 산술 진단은 실제 1x baseline 16행만 사용해 사전등록된 `(1, 2, 3)` 배수 각각을 계산한다.

```text
diagnostic_net_pnl = baseline_net_pnl
                     - (multiplier - 1) * (transaction_cost + fx_cost)
```

이 산술 행은 비용만 추가된 고정 체결 가정이다. 실제 2x 실행의 현금·체결 결과를 대체하지 않으며 MDD, feasibility, 노출 대비 수익률 순위, param search, policy activation을 주장하지 않는다. PAPER 10% 제한은 유지되며 주문을 제출하지 않는다.

실제 frozen run에서 continuous 기간 c2-c1은 control 거래 수 171→174(차이 +3), variant 308→313(차이 +5)였고, 두 arm 모두 순손익 차이는 음수였다. 이는 비용과 체결 변화의 기술적 관찰이며 정책 채택 판정이 아니다. 전체 원자료와 전체 행은 durable audit의 `luna-analysis-final3` 산출물(`diagnostics.json`, `daily.csv`, `comparisons.csv`, `arithmetic.csv`, `assumptionsmanifest.json`)에서 재현한다.

재현 명령은 다음과 같다.

```bash
cd /home/kwl/projects/jusik/backend
.venv/bin/python -m jusik.research_portfolio_exposure_cost \
  --input-dir /home/kwl/.local/share/jusik/portfolio-audit/20260911T132132Z-worktree-development/unheld-entry-real32 \
  --output-dir /home/kwl/.local/share/jusik/portfolio-audit/portfolio-exposure-cost-reproduction-YYYYMMDDTHHMMSSZ
```

`YYYYMMDDTHHMMSSZ`는 실행 시각으로 바꾸고, output 디렉터리는 존재하지 않는 새 경로를 사용해야 한다. 프로그램은 기존 output 덮어쓰기를 거부한다. 최종 산출물 디렉터리는 durable audit의 `luna-analysis-final3`이며, `luna-analysis-final4`에 한 번 더 실행해 모든 파일 바이트가 일치함을 확인했다. 최신 실행 로그와 환경은 `luna-final2-pytest.log`, `luna-final2-ruff.log`, `luna-final2-mypy.log`에 보존했다.
