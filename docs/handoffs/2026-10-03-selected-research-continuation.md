# 등록 종목 연구 계속 진행

- 갱신 2026-10-03T14:08:21.774830+00:00; 현재 사용자는 단계 검증 후 다음 단계 진행을 승인했다. 새 확인을 기다리지 않는다.
- 먼저 MEMORY.md, 등록API revision/목록, Git·writer·관련 등록부 상태를 확인한다. 현재 등록16/rev1, runner inactive/governancefalse. 사용자 root HANDOFF.md를 보존한다.
- 이번 완료: cap-control7fab35e→main de9153d/83검사·독립PASS, 기존baseline전체출력 동일. [회계 인계](2026-10-03-approved-buy-hold-cap-control-20261003.md). 실제수익성미검증.
- 원주가: Alpaca SIP/raw 등록US10 신규1회7931봉·독립PASS. 고정달력 내부/후행누락0, NVDA2024-06-10고가195.95vs123.10차이 미해결. ARM/GEV개시경계 공식원문 추가PASS. [원주가 인계](2026-10-03-selected-alpaca-raw-source-20261003.md). 재조회 대신 기존원문 사용.
- 배당: NVIDIA 기존SEC3건의 record/ex-date 혼용 정정, 금액/기준일/지급일만 partial3 실제반영. eligible24/111, coverageSHA1800dee72e91518fe771d60640229207045019c5529ec6594510bb4cd49205ba. [배당 인계](2026-10-03-selected-us-dividend-next-20261003.md). 같은 SEC원문을 fullmatch로 승격하지 않는다.
- 다음 우선 작업: 기존공식배당/분할/달력/환율/비용 근거 중 실제 소비 필드 결손을 좁혀 보완한다. 원주가 시가/종가를 현 순수회계 입력에 연결할 때 신원·필드별수용·사건시간 결속을 검토하고 고가차이는 남긴다. 새source 없이 같은blocked audit를 재생성하지 않는다. GOOGL10 미검증과 NVDA남은 ex-date가 배당후보다. 현 계좌실제비용은미확정; 가정비용을실제라고표시하지 않는다.
- 이후: 동조건 단순보유/사전등록후보최대3(현재2) 비교, 사용하지않은미래구간. 이미본과거를untouchedOOS라하지않는다. 자본1억·레버리지20%·MDD20%유지. 주문/PAPER/live·GitHubPages·원격push·추가결제·credential정책변경금지.
- 모든 구현/검토CLI 종료, 단일 code writer 없음. 관리형checkout `/home/kwl/.codex/worktrees/official-dividend-input/jusik` clean/reuse가능. native세션한도 오류가 지속하면 기존standaloneCLI세션 재개 가능: code01a101e4-af50-7242-a80b-38e39abd6672,review01a101ef-ad38-73b3-8758-3d376d76f9fd,explore01a101db-2b98-7813-a412-63418263ff55,plan01a101de-0d5f-7881-b2de-c09d33f2d938. 중앙routing resolve/check와 실제metadata를 대조하고 중복writer금지.

## 2026-10-03T14:43Z 후속

- TQQQ공식13건 불일치 검토 반영, 적격24/111 유지. coverage SHA88b7b28028d713c5a77ed2ae0ead36b62b337efd79b883c858778de4aaded1d1. 작업별 selected-tqqq-official-source-20261003 인계가 최신원본. 공식currency/sharebasis 미확인; 반올림추측으로승격금지.
- 두후보설정f4de839독립PASS/main6ca71bb통합, config d329766d... 실행차단유지. 해당작업인계참조.
- 배당상태 latestrevision/latestreview API/UI code 구현중: 관리형 official-dividend-input checkout/codex/approved-dividend-review-status, codeCLI01a101e4-af50-7242-a80b-38e39abd6672. 단일writer유지.
- 후속 selected-candidate-ledger-bridge explore완료/plan진행. 기존원장중복없이 synthetic 연결검증 계획, 실제성과실행금지.

## 배당 UI 통합 후

- approved-dividend-review-status main2aa6f9e 및현재웹반영완료, 해당인계참조.
- selected-candidate-ledger-bridge plan완료/단일Sol코드구현중. checkout `/home/kwl/.codex/worktrees/official-dividend-input/jusik`, branch codex/selected-candidate-ledger-bridge, `/tmp/candidate-bridge-code-events.jsonl`. 기존CLI01a101e4-af50-7242-a80b-38e39abd6672 소유유지.

## 목표 체결 연결 통합 후

- selected-candidate-ledger-bridge main e9d396c 완료. 98검사/독립review/oracle/전체기존출력동일성PASS; 작업별인계참조. 현재appwriter없음.
- 다음source KODEX487230 1회rawreceipt: /tmp/kodex-raw-receipt/collect.py 실행전검토중. source계획의token0조건은감독내부상한이었으며정상기존인증1+quote1로조정, 사용자권한/정책불변. 실제조회아직0.
