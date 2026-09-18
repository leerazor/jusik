# Prospective OOS gate 대기

## 판정

R5의 최종 untouched OOS를 아직 실행하지 않았다. 사전등록된 `research_prospective_registration` 계약의 평가 구간은 `[2026-09-14, 2026-11-09)`이며, 현재 기준일 2026-09-18에는 구간이 진행 중이다.

## 확인한 근거

- 기존 historical robustness: 7 folds, 147 evaluations, 774 union dates. 고정 과거 자료를 반복한 walk-forward 성격의 검토이며 새 미래 holdout이 아니다.
- corrected calendar portfolio bundle: historical approximate simulation이며 마지막 관측일은 2026-09-08이다. 이 결과를 prospective OOS로 이름만 바꾸거나 재사용하지 않는다.
- prospective 계약 identity: source run `fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687`와 등록된 session·policy·code/calendar hash를 유지한다.

## 차단 사유와 안전 조치

종료 전에는 `[start, end)`의 fill provenance와 시작·종료 raw boundary artifact, 승인된 경계 NAV, `evaluation_inputs_complete=true`를 완성할 수 없다. 따라서 지금 성과를 계산하거나 후보를 재선택하면 holdout 누수와 사후 튜닝 위험이 생긴다. historical 결과는 OOS 합격으로 승격하지 않았고, stress 결과도 후보 승격·PAPER 근거로 사용하지 않는다. runner, service, network collection, broker order, PAPER/live 상태는 변경하지 않았다.

## 재개 절차

2026-11-09 이후 고정 계약의 자료와 SHA를 읽기 전용으로 검증한다. 경계 NAV와 completeness가 승인된 경우에만 사전등록된 기준으로 OOS를 단회 계산하고, CAGR·MDD·Sharpe·Calmar와 거래 횟수·회복 기간·비용 등 diagnostic을 함께 기록한다. `MDD > 20%`, required return 미달, 자료 결함 또는 경계 미승인 중 하나라도 있으면 go/no-go는 실패이며 stress/PAPER를 진행하지 않는다.
