# 등록 종목 연구 연속 진행 인계

- 최근 갱신: 2026-10-03T19:50+00:00; root /home/kwl/projects/jusik, 사용자 root HANDOFF.md 보존.
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

## 현재 단계 — 다음 시작

- 위험정책 main7cc20002 이후 동일 조건 비교도 **main18513cde7dc73b12abacdc0fcb6755fe99a37be6 통합 완료**. 구현62f1a759, 독립 review PASS, worker268+132·main132·Ruff/mypy·독립Fraction8사례 PASS.
- 자세한 계약/증거는 2026-10-04-selected-kr-comparison-20261004.md 개발 기록과 인계. 영구audit20261004-selected-kr-comparison manifest09518510... 재사용. 실제 성과나 투자 적격은 아직 미검증.
- 구현 writer 종료, checkout /home/kwl/.codex/worktrees/official-dividend-input/jusik, codex/selected-kr-comparison clean. 다음 안전한 작업에 재사용 가능. 사용자 HANDOFF.md 보존.
- 종료 **selected-next-evidence-20261004 읽기 전용 탐색**: 기존Luna/medium CLI01a101db-2b98-7813-a412-63418263ff55 exec94065. /tmp/selected-next-evidence-explore-events.jsonl 및 결과 파일. 실제 READY cohort 없음. 2026-04-15~08-31 KRX 역사 운영/특별세션·전체action완전성 필요. 같은이름 개발기록/인계의 재개조건 참조. 활성 writer 없음.
- 새 조사 전에 위 결과를 확인. 등록16/revision1, 배당 matched24/mismatched13/partial6/unreviewed68=111은 전체자료준비율이 아니다. KIS HTTP500 동일요청 반복금지. 가격/배당/달력/비용의 같은기간 결속과 실제READYcohort 미확인.
- 100M/레버리지20/MDD20 유지. 주문·승격·원격push·서비스변경 없음.

## 실행 도구·중복 방지

- 중앙정책hash883368a9...; 매dispatchresolve/check. native child한도/parent미로드 실패는반복하지않는다. bounded standalone codex exec resume fallback을쓰고 actual turn_context model/effort/cwd를확인한다.
- CLI explore01a101db-2b98-7813-a412-63418263ff55 Luna/medium; plan01a101de-0d5f-7881-b2de-c09d33f2d938 Sol/high; review01a101ef-ad38-73b3-8758-3d376d76f9fd Sol/high. 현재독립source검토들은종료.
- Node /home/kwl/.nvm/versions/node/v24.20.0/bin; worktree frontenddependencies445 offline설치완료. 현재preview서버는종료했다. 운영webstack active/3000·research8001, 기존인증유지.
- 사용자변경·credential·rootHANDOFF 보존. 신규조사전에최신등록목록/작업등록부/Git/writer를확인하고동일캐시·실패조회·완료검사를반복하지않는다.
