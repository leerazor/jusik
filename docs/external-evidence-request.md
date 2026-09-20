# 외부 증거 입력 요청

이 문서는 현재 경제 평가를 재개하는 데 필요한 외부 입력만 정리합니다. 비밀값은
문서·Git·로그에 기록하지 않습니다.

## SEC 기업행사 검토

검토 대상은 8개이며 양식과 원문은 다음 위치에 있습니다.

- 양식: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/pure-action-review-form.json`
- priority reference catalog: 같은 디렉터리의 `pure-action-review-priority.json`
- 전체 source queue: 같은 디렉터리의 `event-near-review-queue.json` (52개 원문 source gate용)
- 원문: 같은 디렉터리의 `event-near-candidates/`

각 item에 대해 원문을 확인하고 `operator_verified`, `revision_id`,
`content_sha256`, `manual_classification`, `event_type`, `pit_link`를 채웁니다.

작업 순서는 priority catalog의 accession을 원문 filename과 대조하고, 원문에서 확인되는
사실만 양식에 입력하는 것입니다. 시작 전 양식을 별도 복사해 두며, 원문에 없는 날짜·금액·비율은
추정하지 않고 빈 값으로 둡니다.

```bash
cp /home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/pure-action-review-form.json \
  /home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/pure-action-review-form.operator.json
```

- dividend: `amount`, `currency`, `ex_dividend_date`, `comparable_share_basis`
- split: `numerator`, `denominator`, `legal_effective_date`, `comparable_share_basis`

검증 명령:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.research_sec_evidence \
  --validate-review-form /path/to/pure-action-review-form.json \
  --review-candidate-dir /home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/event-near-candidates \
  --review-reference-queue /home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/pure-action-review-priority.json
```

`ready=true`, exit `0`이어야 다음 `ReviewManifest` 검토를 시작할 수 있습니다. 이 결과도
자동 ledger/NAV 적용이나 PAPER 승격을 의미하지 않습니다.

## FX 원천

선택지는 한국수출입은행 Open API입니다. 공공데이터포털에서 활용신청 후 발급된 서비스키를
`.env`의 `KOREAEXIM_API_KEY`에만 저장합니다. `KOREA_EXIM_API_KEY` alias도 지원합니다.
키 값은 채팅·문서·커밋에 붙여 넣지 않습니다. 키가 준비되면 bounded USD/KRW probe와
publication/availability timestamp 계약을 별도로 검증합니다. 발급 화면은
`https://www.data.go.kr/data/3068846/openapi.do`이며, 키가 있어도 응답에 거래일 cutoff를
증명할 publication/availability timestamp가 없으면 FX·Sharpe·NAV 적용은 계속 차단합니다.

ECB reference rate는 키 없이 조회할 수 있지만 historical row별 first-seen 시각이 없어
현재 적용 원천으로 승인하지 않았습니다. ECB의 일반 공표 일정만으로 적용하려면 별도
보수적 availability 정책을 먼저 승인·고정해야 합니다.

## realized P&L

Profit Factor·최대 연속 손실을 계산하려면 canonical trade row마다 명시적인
`realized_pnl_krw`와 lot/position close identity·원가 배분 근거가 필요합니다. 매수/매도
수량만으로 FIFO나 평균법을 추정하지 않습니다.
