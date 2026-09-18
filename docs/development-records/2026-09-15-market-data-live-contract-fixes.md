# Live market data contract fixes

- 상태: 완료
- 기록 시각: 2026-09-15T01:11:30Z
- 작업 slug: `market-data-live-contract-fixes`
- 기준/통합: `e608835` / `fee4eddb21e022fe3a89c4d269a7ed53fc03a06d`
- 범위: 공식 시장자료 요청·정규화·설정·캐시 상태 계약과 관련 회귀 검증을 보완했습니다. 주문·전략·프런트엔드는 변경하지 않았습니다.

## 변경과 결정

- KRX 일별 자료를 공식 `data-dbg.krx.co.kr` board별 GET endpoint와 `basDd` query, `AUTH_KEY` header로 요청하고 응답 envelope·일자·board를 검증합니다.
- Alpha Vantage CSV 전체 header를 검증하고 상품·거래소·이름·날짜·중복 오류를 행 단위로 제외하며 checkpoint별 입력·허용·제외 사유를 limitation에 기록합니다.
- 명시적 dotenv 파일과 표준/alias 환경변수 precedence를 지원하고 보간·프로세스 환경 변이는 사용하지 않습니다.
- collector cache와 completion contract를 v2로 올려 이전 marker를 재사용하지 않으며, `collect-status`가 손상된 cache를 원시 내용 없이 `ready:false`와 종료 코드 2로 보고합니다.
- Yahoo의 NASDAQ Global/Capital Market 식별자인 `NMS`·`NGM`·`NCM`을 Alpha Vantage의 NASDAQ 정규화 결과와 일치시킵니다. NYSE·NYSE Arca 식별자는 교차 허용하지 않습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md`, `.env.example`, `.env.dev.example`에 provider endpoint·env-file·행 단위 exclusion 계약을 반영했습니다.
- 운영 문서: 실제 provider smoke와 US 1년 파일럿의 범위·제외·hash를 아래에 기록했습니다.
- API·설정·데이터 계약: 손상 캐시는 유효한 완료 수집으로 재사용하지 않으며 normalization·cache·completion 계약 버전을 갱신했습니다.

## 검증

- 작업 및 통합 main에서 collector·approximate·market research·runner planning pytest 99개 — 통과
- `backend/.venv-verify/bin/ruff format --check ...` 및 `ruff check ...` — 통과
- strict mypy 관련 9개 source — 통과
- `git diff --check` — 통과
- Next.js production build, 로컬 `/research/market`·API 200, ngrok 비인증 401 — 통과
- 독립 review — KRX 손상 행 fail-closed, 잘못된 budget 구조화 exit 2와 입력 비노출, 인증 실패 비재시도·비캐시, NCM 허용 범위를 직접 확인했고 최종 P1/P2가 없습니다.

## 안전·운영 상태

- `.env`와 `.env.dev`는 mode 600을 유지했고 값은 출력·복사·기록하지 않았습니다.
- 공식 KRX KOSPI·KOSDAQ 호출은 `krx authentication was rejected`로 종료됐으며 응답을 성공 cache나 한국 자료로 저장하지 않았습니다.
- US 2종목 smoke는 Alpha Vantage·Yahoo·FRED를 거쳐 완료됐고, 동일 명령의 재개와 `collect-status`가 manifest 불변·`ready:true`를 확인했습니다.
- US 1년 안정 자료는 2025-09-12~2026-09-11, 고정 표본 100개 중 40개, 대상 거래일 251개, universe 10,840행·bar 10,476행·FX 271행입니다. 배당·분할·부분 또는 무응답·identity 불일치 60종목은 제외했습니다.
- 웹 API의 2025-09-11~2026-09-11 무료 근사 파일럿은 원화 1억원에서 83,066,975.13원, 수익률 -16.9330%, 최대 낙폭 26.4631%, 106회 거래로 완료했습니다. 이는 40종목 표본과 배당 미반영 조건의 근사 결과이며 모델 채택이나 자동 거래 근거가 아닙니다.
- 서비스를 재배포했고 자동 development runner service/timer는 inactive를 유지했습니다. 원격 push와 실제 주문은 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes`
- US 1년 manifest SHA-256: `a806c1ac0058901bbbca007aa91c8f8a3c56bc397c37452025babe82d6260d14`
- US prepared file SHA-256: `e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea`
- 웹 파일럿 응답 SHA-256: `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`
- 남은 작업·차단 조건: 한국은 KRX 포털에서 KOSPI·KOSDAQ 일별매매정보 이용 승인 또는 키 상태 확인이 필요합니다. 미국 결과는 배당 현금흐름·분할 조정 없이 배당 종목을 제외하므로 다음 전략 판단 전에 이 선택 편향을 줄여야 합니다.
- 다음 시작: KRX 승인 상태를 확인하고 한국 제한 smoke를 재실행합니다. 별도 후속으로 미국 배당/기업행동 처리와 수익률 곡선 표시 범위를 정합니다.
