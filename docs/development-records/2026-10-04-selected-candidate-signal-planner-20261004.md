# 선정 후보 합성 신호 계산

- 상태: 완료: 독립 재검토 PASS, 로컬 main 통합·189개 통합 검사 PASS
- 기록 시각: 2026-10-03T16:04:58Z
- 작업 slug: `selected-candidate-signal-planner-20261004`
- 기준/통합: `deedfb0f618b64fd927db0d560c8dc17e49c21c2` / `4e1ff562aad56ed287762345e3a74e088d35308f`
- 범위: 동결된 `equal/none`, `inverse_volatility/none`의 순수 SMA·목표 비중·변동성 축소만 합성 입력으로 계산했다. raw 회계·legacy 원장·서비스·성과 실행은 변경하지 않았다.

## 변경과 결정

- `backend/jusik/selected_candidate_signals.py`: 전체 등록 identity와 cohort, 명시적 synthetic attestation, 설정 바이트 SHA-256, source/calendar hash 형식, 조정가 basis·revision·인과적 시각을 확인한다. 설정의 수치·수식 문구와 등록 revision을 읽어 동결 계약을 검사한다. 설정 파일에는 자기 hash를 저장하지 않는다.
- 자산별 완료·공개 61종가와 SMA20을 분리하고, inverse 후보만 자산 자체 최근 60수익률의 Decimal population 표준편차를 사용한다. eligible 원가중치를 gross 0.60·종목 0.20으로 cap/재배분한 뒤 등록 `leveraged` 합계 0.20을 비례 축소한다.
- 양의 비중이 있으면 전체 cohort의 결정 전 61개 UTC 종가 날짜에 대해 각 일말의 공개 revision과 유효·공개 USD/KRW를 다시 고른다. KRW는 FX가 필요 없다. 60개 global 수익률의 가중 annualized proxy로 최종 비중을 축소한다. `ready`에는 전 cohort의 0 포함 pre-scale/최종 목표·현금이 있고, `incomplete`에는 실행 가능한 목표가 없다. 결과는 `synthetic_reference_only`·투자 `not_evaluated`다.
- `backend/tests/test_selected_candidate_signals.py`: 네 자산 독립 σ 비율 oracle, cap·레버리지·현금, 0/결손, close·FX 공개 cutoff·revision, 동일 시각과 순서, 신원 충돌·원시 basis·비정상 값 검증을 추가했다. legacy 숫자 대사는 회계 `simulate()` 없이 순수 가중치 수식만 사용했다.

## 문서·계약 영향

- `docs/research/approved-universe-comparison-protocol-v1.md`: 네 번째 합성 단계와 신호/체결 경계, 미구현 일정·위험·성과를 기록했다.
- `docs/research/selected-candidate-config-v1.json`: 새 신호 모듈 SHA-256 `12dce485bd069dede64ef64611d8b2a6ec6d3fbd676bb8370fc6bd27c5a6effe`로 갱신했다. 기존 네 의미 source hash와 수치·시점은 동일하며 `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`를 유지한다. 설정 파일 SHA-256은 `e6acafa1c869aa4edb1dff48b2c7d975f466ca937fb2c3583db6a440841e05bc`이다.
- API·운영·서비스 계약: 변경 없음.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_selected_candidate_signals.py backend/tests/test_approved_universe_target_bridge.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_approved_universe_cap_control.py backend/tests/test_market_history_action_accounting.py backend/tests/test_research_portfolio.py backend/tests/test_research_portfolio_time_evidence.py backend/tests/test_research_portfolio_volatility_target_sensitivity.py` — 189개 통과(기존 raw 관련 98개 포함, 신규 24개).
- `backend/.venv/bin/ruff check` 및 `ruff format --check` — 신설 두 파일 통과. `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` — 신설 두 파일 통과.
- `/tmp/buyhold-baseline-compat.py`와 `/tmp/selected-target-bridge-code/cap_compat.py` — baseline 3사례 전체 직렬화 SHA-256 `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`, cap-control KR1%·KR2%·US 전체 직렬화 SHA-256 `90a70498db03492a0ba91a47aeeecbe5e75552d89b9e64938fc01e81c4b535ee`; 사전 고정 JSON과 각각 byte 동일.
- `/tmp/selected-signal-code/independent_oracle.py` — equal `0.15×4`, inverse `0.20,0.20,0.10,0.10`; 독립 population proxy와 legacy 순수 가중치 숫자 허용오차 `1e-12` 대조 통과. 원장·성과 실행 없음.
- 실행하지 않은 검사: 실제 원천 수용, scheduler/밴드/episode/재진입/다종목 체결, 비용 차감 성과는 이 단계 밖이다.

## 안전·운영 상태

- 운영 DB·원천/API·네트워크·runner·서비스·PAPER/실주문·성과 실험·원격 push 변경 없음. 입력 attestation의 hash 형식만 확인하며 원천을 인증했다고 주장하지 않는다.

## 증거와 재개

- 합성 재현: `/tmp/selected-signal-code/`에 독립 oracle, baseline·cap-control 전체 직렬화 출력이 있다.
- 남은 작업: 독립 검토와 로컬 통합은 완료했다. 이후 다종목 목표를 raw 원장에 연결하고 일정·밴드·위험 episode와 실제 입력 적격을 별도 검증한다.
- 다음 시작: 다종목 초기 체결 계획을 읽고 기존 raw core에 제한된 batch를 구현한다.

## workflow 평가

- workflow 판단: 도움 됨 — 계획과 기존 회계 회귀 기준을 재사용해 순수 신호 계산까지만 구현했다.
- 근거: 합성 독립 oracle·legacy 숫자 대사, 189개 회귀, 전체 직렬화 byte 동일을 확인했다. 시간·호출 절감량은 미측정이다.
- 다음 조정: 유지 — 독립 검토 뒤 별도 raw 체결 단계로 진행한다.

## 독립 검토 P2 후속 수정

- 기준: 첫 구현 커밋 `54fbca80054a9d2ef3457f99e40c6bf3e50bbe3c`. UTC와 동등한 `+09:00` aware 시각을 거부하고 지역 날짜가 UTC 표본 날짜·FX 7일 판정에 섞일 수 있다는 P2 지적을 반영했다.
- `plan_selected_candidate` 진입에서 결정, 공식 종가, 종가 공개, FX 유효·공개 시각을 UTC 순간으로 정규화한다. 그 뒤 identity별 UTC 날짜 충돌·revision 키, as-of 공개, global 날짜와 FX calendar age를 검증·계산한다. naive 시각은 계속 거부한다. UTC 입력의 기존 출력 필드는 유지한다.
- 회귀 네 사례: 전체 입력의 UTC↔`+09:00` 동일 결과(지역 날짜는 달라짐), FX UTC 7일 허용/8일 결손 경계, 동등 순간의 종가·FX revision 및 중복 키, 다섯 시각 필드의 naive 거부.
- `/tmp/selected-signal-code/utc_signal_compat.py`로 config hash 갱신 전에 기존 UTC equal·inverse·all-cash 전체 직렬화 SHA-256 `3ef41fbc3c870d8dc05385a4268ba161d940742fcd3fbb00406a84cd63f23602`가 수정 전후 byte 동일함을 확인했다. config 자체의 갱신은 위 hash에 반영했다.
- 최종 189개 회귀, Ruff check/format, strict mypy, 독립 네 자산 oracle 통과. baseline 3사례와 cap-control 3사례 전체 직렬화가 기존 고정 파일과 byte 동일하며 기존 네 소스·신규 모듈 hash와 실행 차단 flags를 확인했다. 재현 경로는 `/tmp/selected-signal-code/`이다.

## supervisor 통합 검증

- 독립 검토: 54fbca8의 시차 P2를 동일 소유자가 a7fc5a6에서 수정했고 독립 +09:00/-04:00·UTC 날짜·FX 7/8일·revision 검증 PASS.
- main4e1ff56에서 189개 검사(6.23초), Ruff·strict mypy, 독립 네 자산 산술·순열·미래 revision probe PASS. sandbox의 TestClient 대기 프로세스만 종료 후 정상 실행 환경에서 같은 검사가 통과했다. 운영 서비스는 변경하지 않았다.
- 영구 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-signal-planner/`; 최초 manifest SHA `fe7f75d0f9d166f7d72d618bc6f3000ff1606691859ae38f9aeb686174e4e0a4`. 통합 검사 로그는 별도 `main-validation.txt`로 보존.
- 다음: 같은 통화·같은 시가의 초기 다종목 target batch를 기존 raw 원장에 연결. 신호·체결 각각의 합성 검증은 실제 수익성이나 전체 전략 완료가 아니다.
