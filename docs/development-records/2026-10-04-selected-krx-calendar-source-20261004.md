# KRX 거래일 근거의 제한된 대조

- 상태: 부분 근거 완료. 연간 공식 달력과 과거 세션 시각 인수는 차단 상태 유지.
- 작업: selected-krx-calendar-source-20261004; 공식 HTML 보존 UTC2026-10-03T15:33:10Z.
- 변경: 코드·DB·성과·주문·서비스·원격 push 없음.

## 확인한 공식 근거와 대사

- [KRX 거래시간·휴장 일반 규칙](https://global.krx.co.kr/contents/GLB/06/0602/0602020204/GLB0602020204T1.jsp): 현재 정규 거래 09:00~15:30 및 토요일·공휴일 등 일반 휴장 규칙을 확인했다. 현재 안내만으로 모든 과거 세션 시각을 인증하지 않는다.
- [KASI의 우주항공청 2026년 월력요항 발표 게시](https://www.kasi.re.kr/kor/post/newsMaterial/32031): 2025-06-30 게시 본문에서 추석 연휴 2026-09-24~27을 확인했다. 해당 일반 공휴일 근거이며 추가 KRX 임시휴장 여부를 증명하지 않는다.
- 2026-09-01~10-02 평일24일에서9/24·25를 제외한22일이 확보한487230 일봉22일과 일치했다. 누락0/예상외0, 독립 재계산 PASS.
- KRX 동적 연도별 휴장일 화면은 첫 열기에서 연도2026 선택 항목만 보였고, 후속 조회 시도는TimeoutError였다. 원인 단계는 확인하지 못했고 같은 요청은 재시도하지 않았다. 모의 생성 거래일이나 정부 달력만으로 연간 거래소 달력 인수를 선언하지 않았다.
- official_calendar_complete=false, historical_session_times_verified=false, nav_ready=false 유지.

## 증거·재개

- audit: /home/kwl/.local/share/jusik/portfolio-audit/20261004-krx-calendar-source/. 공식 HTML2개·수신시각/hash·읽기전용 화면·날짜대사·독립검토·manifest 보존.
- 재개 조건: 정확한 평가 기간의 거래소 연도별 휴장/특별 세션 원문 또는 동등한 공식 날짜별 증거가 확보되면 검토한다. 기존 URL 실패를 같은 상태로 재시도하지 않는다.
- 독립 READY 작업인 selected-candidate-signal-planner-20261004를 계속한다. 실제 수익성 검증을 공학 검사로 대체하지 않는다.
- workflow 판단: 도움 됨 — 동적 화면 실패 후 공식 대체 근거로 좁은 날짜 대사를 수행했지만 인수 한도를 지켰다. 절감량 미측정, 다음에는 같은 보존 근거를 재사용한다.
