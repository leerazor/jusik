# 2026 XKRX 임시·복원 공휴일 달력 정정

## 목적

기존 `exchange_calendars==4.12` 산출물이 2026-06-03 지방선거일과 2026-07-17 제헌절을 XKRX 세션으로 표시해, 고정 portfolio bundle의 저장 NAV chronology와 공식 close union이 1,174 대 1,172로 어긋났다. 원자료를 합성하거나 NAV를 보간하지 않고 versioned calendar override로 원인을 교정한다.

## 근거와 변경

- 한국거래소 휴장 공지 보도: `https://www.yna.co.kr/view/AKR20260520064251008`
- 한국은행 2026 holiday schedule: `https://www.bok.or.kr/eng/main/contents.do?menuNo=400373`
- `backend/scripts/generate_market_calendar.py`에 두 날짜의 XKRX `closed` override와 provenance를 추가했다.
- XNYS 및 다른 XKRX 세션은 변경하지 않는다. 기존 audit bundle은 덮어쓰지 않는다.

## 검증

- 새 생성 calendar payload SHA: `5ac707711cb82f7849b7824567515f67dcbaad162452757b6727cccb9e20f2bd`
- `test_research_market_calendar.py`: 10 passed (`uv run --with pytest --with exchange_calendars==4.12`)
- 생성 결과에서 두 날짜가 XKRX `closed`, XNYS는 기존 session으로 유지됨을 read-only JSON 대조했다.
- 실제 simulation, 주문, runner 재개는 수행하지 않았다.

## 다음 단계

새 calendar artifact를 별도 입력 identity로 묶어 fixed input preflight와 독립 accounting을 다시 검증한 뒤, required sessions가 1,172로 일치할 때만 metrics adapter 작업을 재개한다.
