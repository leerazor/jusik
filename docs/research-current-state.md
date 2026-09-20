# 현재 연구 상태와 다음 방향

- 기준일: 2026-09-21 (Asia/Seoul)
- 저장소: `main`, 원격 push 없음, Windows 종료 없음
- 운영: development runner paused, service inactive, timer disabled
- 현재 판단: 전략 파라미터를 바꾸거나 후보를 추가할 단계가 아니다. 미국 자료·회계·원가·PIT gate를 먼저 닫고 같은 정책을 재실행한다.

## 현재까지 확인된 결과

| 영역 | 확인 결과 | 판정 |
| --- | --- | --- |
| 기존 미국 1년 기준 실행 | 초기 100,000,000 KRW → 83,066,975.13 KRW, 순수익 `-16.933%`, MDD `26.463%`, 거래 `106`건 | 경제적으로 MDD 20% hard filter 실패 |
| 미국 bounded 재수집 | universe 17,310, bars 17,263, FX 272, events 104; 기업행사 35개는 PIT 시각 불명 | 수집 성공이나 `status=insufficient`, 성과 미계산 |
| 독립 회계 | 저장 비용·일부 FX·현금은 검산되지만 완전한 fill/opening position/terminal mark/dividend 근거 부족 | R2 경제 평가 `not-evaluated` |
| 기업행사 | SEC priority 8건 source 8/8 결속, 4 action·4 exclude form validator `ready=true` | ledger 자동 적용 금지, R1-04 전체는 미완료 |
| FX | KoreaExim 키 응답 23행/USD 1행 확인; publication/availability timestamp 없음 | historical FX/NAV/Sharpe 적용 차단 |
| 한국 KRX | 2026-06-29 zero OHLCV 29건, 전후 날짜에도 반복; 일별시세 API HTTP 200 | 원인은 정황만 확인, 공식 status 없이는 `insufficient` |
| 한투 비용 | BanKIS online 공식 요율 profile·hash-bound PAPER contract/manifest validator 구현 | frozen historical에는 미적용 |
| 코드/검증 | KRX status adapter, BanKIS cost profile/contract 등 fail-closed 기술 slice 통과 | 기술 기반은 진전, 경제 승격 아님 |

## 해석

현재 `-16.933%`와 `26.463% MDD`는 전략이 채택 가능한 결과라는 근거가 아닙니다. 특히 MDD가 사전 hard filter `20%`를 초과했으므로, 자료 gate를 닫은 뒤에도 같은 정책이 이를 넘으면 해당 전략은 PAPER 후보가 아닙니다.

반대로 지금 즉시 전략을 바꾸면 다음 문제가 생깁니다.

- 기업행사·FX·비용 오류와 전략 신호의 효과를 분리할 수 없음
- 같은 미국 결과를 반복 튜닝해 overfitting 위험 증가
- KRX 결측을 미국 성과 판단에 섞게 됨
- historical provenance mismatch를 덮어쓸 위험

## 권장 진행 방식

1. **미국 자료 gate 우선**: SEC action 4건은 form에만 보존하고 ledger/NAV에 적용하기 전에 PIT·권리·가격 경계를 확인합니다. FX는 publication/availability timestamp가 있는 원천을 확보하거나, 없으면 미국 성과를 `not-evaluated`로 유지합니다.
2. **독립 회계 gate 완료**: complete fills, opening positions, terminal marks, dividend/action evidence를 같은 run에 결속하고 NAV residual·fee·tax·FX를 재대사합니다.
3. **고정 정책 재실행**: 자료 gate가 통과할 때만 동일 정책으로 미국 1년 pilot을 한 번 실행합니다. 결과가 MDD `>20%`면 파라미터 튜닝 없이 전략을 탈락 처리합니다.
4. **그 이후에만 후보 연구**: pilot이 통과할 때만 최대 3개 후보를 사전등록해 IS → hard filter → OOS → walk-forward → stress → isolated simulation 순서로 진행합니다.
5. **한국은 병렬 보조 경로**: KRX status 권한/원문이 확보되면 29개 종목을 adapter로 검증합니다. 그 전에는 한국 benchmark·경제 성과를 만들지 않습니다.

## 계속 개발할 것과 멈출 것

계속할 것:

- evidence/status payload validator와 source hash 결속
- 미국 PIT action·FX·독립 회계 gate
- BanKIS PAPER contract를 새 연구 manifest에 연결
- 실패 원인·coverage·metric을 Markdown과 audit에 기록

멈출 것:

- 현재 전략의 파라미터 retuning
- 같은 holdout 반복 평가
- 수익률 개선을 위한 종목 교체
- KRX zero 행 보간
- PAPER/live 자동 승격

## 다음 작업

- 미국 FX timestamp 대체 원천 또는 timestamp 계약 조사
- SEC action form을 action ledger에 적용하기 전 PIT boundary validator 연결
- 독립 회계 bundle의 누락 입력 목록을 자동 보고
- 위 gate 중 하나가 해소되면 동일 정책 미국 pilot 재실행 여부를 기록

이 문서는 전략 채택 결정이 아니라, 다음 연구를 어떤 순서로 수행할지에 대한 현재 판단이다.
