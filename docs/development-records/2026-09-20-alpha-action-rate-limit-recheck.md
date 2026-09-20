# Alpha action rate-limit recheck

- 기록 시각: 2026-09-20T03:35:00Z
- 목적: US collection에서 `observed_at=null`인 기업행사를 Alpha Vantage `DIVIDENDS`/`SPLITS`
  원문으로 보조 대조할 수 있는지 bounded하게 확인했습니다.

## 결과

- 대상: SEC 후보와 겹치는 31개 심볼, 별도 audit 경로
- 첫 요청에서 Alpha Vantage 표준 일일 25회 rate-limit 응답을 받아 parser가
  `alpha_actions_provider_error`로 fail-closed 종료했습니다.
- 공급자 rate-limit 응답 raw는 API key 재노출 위험이 있어 보존하지 않고 즉시 삭제했습니다.
- 기존 frozen cache, prepared dataset, `.env`, SEC evidence는 변경하지 않았습니다.

## 판정

Alpha key rotation과 새 일일 quota가 확인되기 전에는 이 경로를 재시도하지 않습니다. 현재 SEC
review queue는 보조 후보로만 유지하며, Alpha rate-limit을 자료 성공이나 action 사실로 해석하지
않습니다. R1-04/R4 readiness, ledger 적용, 성과 계산, PAPER/live 승격은 계속 보류합니다.

## 보안 조치

공급자 응답이 credential을 본문에 포함할 수 있으므로 사용 중인 Alpha key는 회전해야 합니다.
새 key는 `.env`에만 저장하고 audit·로그·문서에 값을 기록하지 않습니다.
