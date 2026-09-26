# 3시간 연구 성능 개선 집중 작업

## 범위와 운영

사용자는 토큰 리셋 전 3시간 동안 유용한 성능 개선에 집중하도록 요청했다. 시작은
2026-09-26T07:56:14Z, 종료 목표는 10:56:14Z(19:56 KST)다. 계정의 실제 잔여량·리셋
시각을 조회한 것으로 해석하지 않는다. 추가 결제·권한·credential 변경·투자 기준
완화·실주문·원격 push·Windows 종료는 하지 않는다.

시작 당시 runner는 별도 `research-web-reports` UI 작업으로 pause였고 실행 중인
runner child는 없었다. 그 pause 소유권과 frontend·운영 데이터는 보존한다. 본 작업은
별도 backend worktree와 전용 환경에서 수행하며 main 통합은 활동·HEAD를 다시
확인한 경계에서 직렬로 한다. 다른 사용자의 미추적 `HANDOFF.md`와 UI 기록은 보존한다.

전용 audit:
`/home/kwl/.local/share/jusik/portfolio-audit/20260926-performance-sprint-XzoOxB/`.

## 첫 병목과 확정한 계획

Luna read-only 조사에서 `research_engine.run_backtest`가 전체·학습·검증의 기본/후보
전략을 최대 여섯 번 실행하면서 같은 순수 SMA 신호를 반복 계산함을 확인했다.
10종목×550봉의 합성 입력 cProfile은 총 0.194초, 신호 19,460회·SMA 29,190회였다.
이는 단일 초기 관측이며 제품 speedup 결과는 아니다. 별도 시장 fixture의 1,136봉은
0.031초였고, 이 경로에는 아직 변경 근거를 확정하지 않았다.

별도 Sol 계획에 따라 `research_engine.py` 내부의 한 `run_backtest`에 한정된
`(version, symbol, sorted_bar_index)` bool cache를 검토한다. 기본 신호만 기존
`target_invested`로 계산하고 순서·Decimal precision 40·ROUND_HALF_EVEN·포트폴리오
상태·날짜 인덱스 의미를 유지한다. rolling recurrence, 전역 캐시, 전략 수식 변경,
다른 엔진의 hash pin 변경은 제외한다. 사용자 정의 SMA와 callback 경로는 그대로다.

단일 Sol 구현 파일은 `backend/jusik/research_engine.py`와
`backend/tests/test_research_engine.py`다. 외부 audit의 재현 benchmark와 결과도
같은 구현자가 준비한다. `perf/research-signal-cache` 전용 worktree를 사용한다.

## 검증·완료 기준

- 현재 합법 요청 상한인 10종목, 550/1,100봉 합성 입력을 고정한다.
- 기준/후보 각각 warmup 3회·측정 11회의 median을 교대로 확인한다. 대표 1,100봉에서
  10% 이상 개선을 목표로 하되 벽시계 속도를 CI assertion으로 쓰지 않는다.
- 전체 출력은 `implementation_hash`, `parameters_hash`만 제외해 정확히 비교하고,
  여섯 내부 `StrategyResult`의 거래·자산 경로도 비교한다. 변경된 코드 hash는 별도 확인한다.
- 미래 prefix 불변, 이벤트·수수료·미체결·누락·중복 날짜·역순·Decimal 경계,
  연속 실행의 캐시 격리, 비기본 SMA·callback 동작을 검증한다.
- engine/optimizer/risk/universe 집중 pytest, Ruff, strict mypy, 별도 Sol review,
  main 통합 검증을 통과해야 완료다. 기존 역사 산출물 pin 실패를 숨기지 않는다.

## 독립 연구 준비 점검

root의 정적 계약 점검에서는 legacy prospective 등록의 6개 metric과 현재 mandate의
CAGR/MDD/Sharpe/Calmar·고정 required return·분리 validation/WF/단회 OOS 계약이
같지 않음을 확인했다. 기존 literal `evaluation_inputs_complete=False`는 유지된다.
평가 창은 `[2026-09-14, 2026-11-09)`이며 runtime 등록·관측·PAPER DB·미래 성과는
열지 않았다. 상세는 audit의 `PROSPECTIVE_CONTRACT_AUDIT.md`에 있다. 새 계약의
실제 구현·등록·투자 검증을 이 점검만으로 승인하지 않는다.

## 현재 판정

구현·검증 진행 전 기록이다. 새 speedup 수치, 수익률 개선, 투자 검증 통과를 주장하지
않는다. 후속 결과·커밋·검토·인계는 완료 시 갱신한다.
