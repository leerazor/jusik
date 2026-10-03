# 등록 종목 연구 연속 진행 인계

- 최근 갱신: 2026-10-04 KST / UTC2026-10-03T18:10+00:00. root /home/kwl/projects/jusik, 사용자 root HANDOFF.md 보존.
- 사용자 승인: 한 단계 검증 후 다음 안전한 단계 계속. 등록16/revision1 유지. 자동매매·실주문·PAPER/live·GitHub Pages·원격push·추가결제·credential정책변경·투자기준완화 금지.
- 초기 총1억원·레버리지20%·MDD20% 유지. 과거자료를 untouched OOS로 표시하지 않는다. 기존 runner/timer inactive, governance dispatch false. 기존 heartbeat만 유지.

## 완료·재사용

- 현재 웹의 배당 상태 API/UI: main2aa6f9e, 독립 code/screen 및 실제 API/mobile 확인 완료. 일치·부분·불일치·미검토를 분리하며 null=조회불가. TQQQ불일치13/NVDA부분4/MSFT일치12, 적격전체24/111과별개. approved-dividend-review-status-20261003 인계 참조.
- 두 후보 설정 동결: equal/none·inverse_volatility/none, 연구제어값gross60/symbol20/vol10/episode10%, 사용자hardfilter와구별. sourcehash는 후속구현에맞게갱신하되 execution_allowed=false/results_observed=false/candidate_execution_code_hash=null 유지.
- raw회계: 순수보유·capcontrol 후 합성 단일target 체결까지 main e9d396c 통합. 98tests/Ruff/mypy/독립KR·US·분할후배당oracle/기존6사례전체출력byte동일 PASS. selected-candidate-ledger-bridge-20261003 인계와영구audit재사용.
- 배당: MSFT12+NVDA1+KODEX11 eligible24/111. NVDApartial3 추가와 TQQQmismatched13은미적격. 최신coverage88b7b28028d713c5a77ed2ae0ead36b62b337efd79b883c858778de4aaded1d1. 각selected-us-dividend-next/selected-tqqq-official-source 인계참조. 기존실패조회반복금지.
- US10 raw7931봉 및ARM/GEV상장경계: selected-alpaca-raw-source 인계. NVDA2024-06-10고가차이미해결, 연구인수미완료.
- KODEX487230 현재원주가22봉: 정상auth1+시세1/재시도0, 기존22일OHLCV일치 독립PASS. 2026-10-04-selected-kodex-raw-receipt-20261003 인계. 공개필드추출만보존, 전체원응답미보존; 과거543행lineage/PIT/자료적격을증명하지않는다.
- KRX/KASI 공식근거: 9/1~10/2 예상22일대사PASS. 연간KRX동적조회timeout, official_calendar_complete/historical_session_times_verified/nav_ready false. 2026-10-04-selected-krx-calendar-source-20261004 인계. 같은실패조회재시도금지.
- KIS 새 휴장일 endpoint CTCA0903R: 18:17:48UTC 기존연구host auth1/GET1 → HTTP500, retry0/pagination0, 자료0. `2026-10-04-selected-kis-calendar-receipt-20261004.md` 인계/audit 재사용. 원인미확정, 동일재시도·live전환 금지; 새지원근거/공식거래소자료가 재개조건.
- 비용 실계좌정보0/16은 명시적비용가정시나리오의전역차단조건이아님. KRW ETF원장에불필요USD환전을추가하지않는다. 실제 READYcohort는아직확인못함.

## 현재 단일 writer — 다음 시작

- 신호 main4e1ff56/189검사, 초기batch main42214b8/200검사, KR재조정 main74a5581/208검사에 이어 후보정책 연결 mainb992712/240검사까지 독립 검토·통합 PASS.
- 후보정책 구현856b3c6의 의미소스해시검증 P2를 동일소유자4ad0fa5에서 수정, 독립재검토PASS. 기존11개/KRsequence 전체 출력 보존, 외부 현금·수량·NAV/순서반전4사례 PASS. `2026-10-04-selected-kr-candidate-policy-20261004.md` 인계 및 audit20261004-selected-kr-candidate-policy 재사용.
- 현재 **selected-kr-risk-policy-20261004 독립검토 P2 2건을 동일 구현자 수정 중**. checkout `/home/kwl/.codex/worktrees/official-dividend-input/jusik`, branch `codex/selected-kr-risk-policy`, base32e9d9ad8320e40d1af32fd4f7274bbd1274fc41.
- 소유자 Sol/high CLI01a101e4-af50-7242-a80b-38e39abd6672, 현재 수정 exec session71919. `/tmp/selected-kr-risk-fix-events.jsonl`·stderr, 지시 `/tmp/selected-kr-risk-fix.txt`. 원구현 로그 `/tmp/selected-kr-risk-code-events.jsonl`은 종료. 중복writer 금지.
- 완료된 delta explore/plan: `/tmp/selected-risk-explore-result.txt`, `/tmp/selected-risk-plan-result.txt` 및 직전audit 사본. 다시 조사하지 않는다.
- 범위: 기존 policy/rawcore, 신규risk tests, 규약/confighash/개발기록. 같은원장에 episode10% 위험청산·pending취소·청산완료후28일/주간2회/다음4주재진입·cap우선처리. 구공개계약 및 lifetimeMDD20 이력보존, fullrisk 별도entry 허용. 같은시각신규관측으로같은시가주문 금지.
- 구현8efee89/262검사·독립4사례 PASS이나 독립검토 P2 2건: 비용연쇄 cap 재평가(후순위매도비용으로앞종목위반), 개별첫개장불일치에도 다음공통개장선택 필요. `/tmp/selected-kr-risk-review-result.txt` 재사용. 수정 후 경계 재검토→main통합/관련검사/기록. 아직 main미통합.
- 신규자료 KODEX2종목4/15~8/31 각93봉·기존캐시대사·독립PASS는 `2026-10-04-selected-kodex-warmup-receipt-20261004.md` 재사용. 동일조회금지, calendar/actions/NAV/PIT 준비false 유지.
- 등록16/revision1, 100M/레버리지20/MDD20 유지. runner/timer inactive, webstack active 확인. 운영실행/주문/승격/원격push 없음.

## 실행 도구·중복 방지

- 중앙정책hash883368a9...; 매dispatchresolve/check. native child한도/parent미로드 실패는반복하지않는다. bounded standalone codex exec resume fallback을쓰고 actual turn_context model/effort/cwd를확인한다.
- CLI explore01a101db-2b98-7813-a412-63418263ff55 Luna/medium; plan01a101de-0d5f-7881-b2de-c09d33f2d938 Sol/high; review01a101ef-ad38-73b3-8758-3d376d76f9fd Sol/high. 현재독립source검토들은종료.
- Node /home/kwl/.nvm/versions/node/v24.20.0/bin; worktree frontenddependencies445 offline설치완료. 현재preview서버는종료했다. 운영webstack active/3000·research8001, 기존인증유지.
- 사용자변경·credential·rootHANDOFF 보존. 신규조사전에최신등록목록/작업등록부/Git/writer를확인하고동일캐시·실패조회·완료검사를반복하지않는다.
