# KIS 공개 휴장일 보조 자료 1회 조회

- 상태: 자료 수집 차단, 독립 사전검토와 제한된 실제 시도 완료
- 기록 시각: 2026-10-03T18:17:48Z
- 작업 slug: selected-kis-calendar-receipt-20261004
- 범위: 기존 PAPER 연구 호스트/인증으로 공개 휴장일 자료만 조회. 실행환경·거래 모드 승격 없음.

## 근거와 결과

- 공식 [수집 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/chk_holiday/chk_holiday.py)는 CTCA0903R, `/uapi/domestic-stock/v1/quotations/chk-holiday`, BASS_DT와 연속 키를 사용하며 가급적 하루1회 호출을 권고한다.
- [출력 필드 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/chk_holiday/chk_chk_holiday.py)는 기준일자·요일·영업일·거래일·개장일·결제일을 구분한다. 과거특별개장시각/거래소전체달력/PIT를 증명하는 계약은 아니다.
- 독립 Sol/high 사전검토 PASS. mock 정상 공개필드 추출·업무오류·비밀문자열 차단·반복실행 거부 확인. 실제 요청과 별개다.
- 실제18:17:48UTC, 기준20260415, 기존연구host에서 auth1/GET1/retry0/pagination0. HTTP500, `CALENDAR_HTTP_500`; 데이터0건. 지원 여부/서버장애 원인은 이 응답만으로 단정하지 않는다. 원응답·인증정보 미보존, 상태코드와 안전한receipt만 저장했다.
- 예상 파일명 chk_holiday_chk.py의 문서 조회404는 올바른 공식파일 chk_chk_holiday.py로 해소했다. API 오류와 혼동하지 않는다.

## 경계와 재개

- 동일요청/호스트 재시도 금지. 새 공식 거래소 자료 또는 기존 연구호스트에서 해당 endpoint가 작동한다는 새 외부근거가 생기면 한도·중복을 재확인해 재개한다. live호스트/credential/권한정책 변경으로 우회하지 않는다.
- `nav_ready=false`, `official_exchange_calendar_complete=false`, `historical_session_times_verified=false` 유지. 운영DB·서비스·주문·PAPER/live 승격·원격push 변경 없음.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-kis-calendar-receipt/`, manifest SHA256 `10ae6598309a9a3eb5f86bce804c04126ba19bc3ba8994e1c85068b670f6527c`.
- 사용자/API 계약 변경 없음. 구현 없이 공식 대체근거의 실행 가능성을 확인한 기록이다. 위험 정책 단일 구현은 독립적으로 계속된다.

## workflow 평가

- 도움 됨: 기존 실패경로와 다른 공식 endpoint를 한 번만 제한 조회하고 재시도 차단 근거를 남겼다.
- 근거: 독립 mock검토, auth1/GET1 제한 실제receipt. 시간·호출 절감량 미측정.
- 다음 조정: 동일 실패 반복 대신 새 외부근거가 생길 때 재개한다.
