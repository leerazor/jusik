# 보유 밴드 underwater 기간 분석 v1

이 문서는 고정된 48개 보유 밴드 경로에서 초기 자본을 포함한 running peak 기준 MDD와 고점 회복까지의 underwater 기간을 기술 통계로 산출하는 분석을 설명한다.

각 경로는 UTC 시각이 엄격히 증가하고 중복되지 않으며 비어 있지 않아야 한다. 불규칙한 간격은 그대로 경과 초로 계산하고, 동일 기간의 control/variant 및 cost 1/2/3 여섯 경로는 관측 시각이 같아야 한다. 이 검사는 시장 휴일이나 원천 calendar의 완전성을 추론하지 않는다.

underwater episode는 초기 자본을 포함한 running peak를 기준으로 처음 고점 아래로 내려간 관측에서 시작하고 같은 고점 이상이 된 관측에서 끝난다. 관측 사이에 회복이 있었다고 추정하지 않으며, 마지막 관측까지 회복하지 않으면 우측 검열로 표시하고 `terminal_unrecovered`를 별도로 기록한다. 최장 기간 동률은 시작 시각이 이른 구간을 선택한다.

실행 예:

```bash
python -m jusik.research_portfolio_underwater_duration \
  --input-dir /path/to/portfolio-held-band-cost3-stress-v1/experiment \
  --output-dir /path/to/underwater-duration-output
```

분석은 `research_portfolio_cost_path_attribution.load_frozen`의 고정 SHA, 48개 파일, Decimal 회계 잔차 0.000001 KRW 검증을 재사용한다. 금액 회계·최종 equity 잔차 허용치는 0.000001 KRW이고, 비율로 저장되는 MDD 재계산 대조 허용치는 1e-18(분율)이다. historical simulation, 외부 수집, DB/config/PAPER/GPU 및 주문 호출은 없다. 결과는 fold와 continuous를 분리해 보고하며 MDD 개선과 기간 증가를 인과 효과나 정책 승격으로 해석하지 않는다.

고정 조건은 초기 자본 100,000,000 KRW, 사용자 손실 한도 20%, leveraged ETF 한도 20%, frozen drawdown limit 10%, PAPER limit 10%이다. live 실행은 유보한다. 이 분석은 실시간 위험 통제나 손실 보장을 제공하지 않는다.
