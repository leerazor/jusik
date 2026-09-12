# 진입 금액 분포 분석

`jusik.research_entry_amount_distribution`는 고정된 미보유 진입 실험 32개
(8기간 × 2 arm × 2 cost)의 BUY 체결 금액을 읽기 전용으로 검증하고 분포를
계산한다. 각 BUY는 매수 직전 보유수량이 0이면 `new_entry`, 양수이면
`additional_buy`로 분류한다. 결과를 pooling하지 않고 32개 strata를 유지한다.

금액은 `quantity × local_price × fx_rate`로 계산한 BUY 체결 notional(KRW)이며
`notional_krw`와 Decimal 정밀도로 대조한다. 수수료와 FX 비용은 금액에 포함하지
않고, 체결 가격에 반영된 슬리피지는 포함한다. 기업행동 split을 거래일 순서로
재생하고 최종 보유수량을 원본 simulation과 대조한다. oversell, 입력 해시,
회계 또는 수량 불일치가 발생하면 즉시 중단한다.

분위수는 nearest-rank (`ceil(p × n)`, 1-indexed), 구간은 `<10000`,
`[10000,100000)`, `[100000,1000000)`, `[1000000,10000000)`, `>=10000000`
KRW다. 빈 표본은 합계 0과 `null` 통계로 기록한다.

분석은 기술통계다. 이 결과만으로 거래 임계값이나 거래 제약을 권고하지 않으며,
후향적으로 재사용한 고정 결과이므로 수익·위험의 인과적 설명, PAPER 승격 또는
실거래 근거로 해석하지 않는다.

## 재현

출력 디렉터리는 반드시 새로 만들거나 비어 있어야 한다. 기본 출력 경로는 없으며,
기존 파일이 있는 디렉터리는 `--allow-overwrite` 없이는 거부한다.

```bash
mkdir -p validation/entry-amount-run
PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python \
  -m jusik.research_entry_amount_distribution \
  --input-dir /home/kwl/.local/share/jusik/portfolio-audit/20260911T132132Z-worktree-development/unheld-entry-real32 \
  --source-manifest /home/kwl/.local/share/jusik/portfolio-audit/20260911T060908Z-rebalance-band/source-manifest.json \
  --output-dir validation/entry-amount-run
```

생성물은 `distribution.json`, `distribution.csv`, `buy-events.csv`, `report.md`다.
입력은 `results.json` SHA-256
`5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4`,
`preregistration.json` SHA-256
`9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7`,
source manifest SHA-256
`1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825`로 고정된다.
