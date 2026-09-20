# Research direction checkpoint

- 상태: 완료·미국 자료 gate 우선
- 기록 시각: 2026-09-21T00:00:00Z
- 작업 slug: `research-direction-checkpoint-20260921`
- 기준/통합: `2ee91b7` / 다음 통합 커밋
- 범위: 최근 미국·한국·SEC·FX·비용·회계 결과를 종합해 전략을 계속 개발할지 방향을 점검했습니다. 전략 파라미터·후보·historical artifact는 변경하지 않았습니다.

## 근거

- 기존 미국 기준 run: 순수익 `-16.933%`, MDD `26.463%`, 거래 `106`건. 사전 MDD hard filter `20%`를 초과합니다.
- 미국 bounded 재수집: 기업행사 35개가 PIT 시각 불명으로 `status=insufficient`, `completeness=incomplete`, trades/equity/metrics 0입니다.
- 독립 회계: 비용·일부 FX·현금은 검산됐지만 complete fills/opening positions/terminal marks/dividend evidence가 부족합니다.
- KoreaExim: 키와 USD row는 확인했지만 publication/availability timestamp가 없어 historical FX/NAV/Sharpe 적용이 차단됩니다.
- KRX: HTTP 200 및 29 zero-OHLCV를 확인했으나 공식 status 원문 없이는 거래정지·정상 상태를 확정할 수 없습니다.
- SEC: 4 action/4 exclude form은 `ready=true`지만 자동 원장 적용은 금지됩니다.

## 결정

- 현재 전략을 즉시 retune하거나 새 종목으로 교체하지 않습니다. 그러면 데이터 오류와 전략 효과를 분리할 수 없고 overfitting 위험이 커집니다.
- 미국 FX/PIT/독립 회계 gate를 먼저 닫고, 동일 정책으로 미국 pilot을 한 번만 재실행합니다.
- 그 재실행에서도 MDD가 `20%`를 넘으면 해당 전략은 PAPER 후보에서 제외합니다.
- 한국 성과·benchmark는 KRX status 원문과 zero-row 결속이 확보될 때까지 별도 `insufficient`로 유지합니다.

## 검증·운영

- 근거 기록과 roadmap/task register 대조 완료
- 실제 주문·PAPER/live 승격·remote push·Windows 종료 없음
- runner paused, service inactive, timer disabled

## 다음 시작

- 미국 FX timestamp를 제공하는 대체 원천/계약을 bounded 조사하고, 동시에 독립 회계 누락 입력 보고서를 만든다. 둘 중 하나가 해결되면 같은 정책 pilot 재실행 gate를 검토한다.
