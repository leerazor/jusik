import { researchReportHref } from "@/lib/research-reports";
import Link from "next/link";
import styles from "./forward.module.css";
import { getForwardLedger, getForwardStatus, getProspectiveRegistrationStatus, researchAmount, type ProspectiveRegistrationStatus } from "@/lib/research";

export const dynamic = "force-dynamic";

function kst(value: string): string {
  return `${new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}
const stateLabel: Record<string, string> = {
  observing: "관찰 중", waiting_cadence: "정기 판단 대기", decision_recorded: "결정 기록",
  awaiting_quotes: "유효 시세 대기", completed: "가상 체결 완료 기록", partially_completed: "일부 체결",
  expired: "만료", inputs_blocked: "입력 차단", risk_liquidation: "위험 청산",
  cooldown: "재진입 대기", recovery_wait: "회복 확인", reentry_ready: "재진입 준비",
  disabled: "비활성", connecting: "연결 중", connected: "수신 중", partial: "일부 수신",
  stale: "시세 지연", error: "오류", pending: "첫 시세 대기", rejected: "구독 거부",
  unsupported: "미지원",
};
const stateMeaning: Record<string, string> = {
  observing: "들어오는 가격을 보며 판단에 필요한 기록을 쌓고 있습니다.",
  waiting_cadence: "보유할 종목과 금액을 다시 계산할 예정 시각을 기다리는 상태입니다. 반드시 그때 매매한다는 뜻은 아닙니다.",
  decision_recorded: "프로그램이 무엇을 보유할지 판단을 기록했습니다. 판단을 기록한 것과 가상 매매가 끝난 것은 다릅니다.",
  awaiting_quotes: "가상으로 사고판 가격을 계산하는 데 필요한 시세를 기다립니다.",
  completed: "한 번의 판단에 따른 가상 매매 처리가 끝났다는 기록입니다. 투자 방법의 검증이 끝났다는 뜻은 아닙니다.",
  partially_completed: "가상 매매의 일부만 기록됐습니다. 전체 처리가 완료됐다고 볼 수 없습니다.",
  expired: "이번 판단에 사용할 수 있는 시간이 지났습니다. 다음 판단 기록을 확인해야 합니다.",
  inputs_blocked: "필요한 자료를 사용할 수 없어 판단이나 가상 거래가 제한된 상태입니다. 아래 자료 문제를 확인하세요.",
  risk_liquidation: "손실 대응 규칙에 따라 보유분을 파는 가상 절차를 진행하는 상태입니다.",
  cooldown: "보유분을 정리한 뒤, 바로 다시 사지 않고 기다리는 상태입니다.",
  recovery_wait: "다시 투자할 조건이 회복됐는지 확인하는 상태입니다.",
  reentry_ready: "다시 투자할 준비 조건이 기록됐으며, 다음 정기 판단을 기다립니다.",
};
const phaseLabel: Record<string, string> = {
  queued: "전송 대기", awaiting_ack: "승인 대기", approved: "승인됨", rejected: "구독 거부",
};
const calendarPhaseLabel: Record<string, string> = {
  pre_open: "개장 전", regular_session: "정규장", post_close: "폐장",
  closed: "휴장", unavailable: "달력 미확인",
};
function feedState(state: string, phase: string, overdue: boolean): string {
  if (state !== "pending") return stateLabel[state];
  if (overdue) return "승인 확인 지연";
  if (phase === "queued") return "전송 대기";
  if (phase === "awaiting_ack") return "승인 대기";
  return "승인됨 · 첫 시세 대기";
}
const registrationStateLabel: Record<string, string> = { not_registered: "미등록", planned: "검증 예정", observing: "검증 중", window_elapsed: "검증 창 종료", identity_mismatch: "식별 정보 불일치", invalid_contract: "계약 검증 실패" };

export default async function ForwardResearchPage() {
  let status = null;
  let ledger = null;
  let statusError = false;
  let ledgerError = false;
  let registration: ProspectiveRegistrationStatus | null = null;
  let registrationError = false;
  try {
    const results = await Promise.allSettled([getForwardStatus(), getForwardLedger(), getProspectiveRegistrationStatus()]);
    if (results[0].status === "fulfilled") status = results[0].value;
    else statusError = true;
    if (results[1].status === "fulfilled") ledger = results[1].value;
    else ledgerError = true;
    if (results[2].status === "fulfilled") registration = results[2].value;
    else registrationError = true;
  } catch {
    statusError = true;
    ledgerError = true;
    registrationError = true;
  }
  const registered = registration?.registration;
  const identityMatches = Boolean(status && registered && registered.session_id === status.session.id && registered.policy_hash === status.session.policy_hash && registered.source_run_id === status.session.source_run_id && registration?.status !== "identity_mismatch" && registration?.status !== "invalid_contract");
  const registrationLabel = registrationError || !registration || !status ? "자료를 확인하지 못함" : registration.status === "not_registered" ? "검증 계획 미등록" : registration.status === "invalid_contract" ? "검증 계획의 형식을 확인하지 못함" : !identityMatches ? "현재 계좌와 검증 계획의 대상이 다름" : registrationStateLabel[registration.status];
  const registrationProblem = registrationError || !registration || !status ? "검증 계획과 현재 계좌를 함께 확인할 수 없습니다" : registration.status === "invalid_contract" ? "등록된 검증 계획을 읽을 수 없습니다" : "현재 가상 계좌가 등록된 검증 대상과 맞지 않습니다";
  return (
    <main className={styles.main}>
      <section className={styles.hero}><p className={styles.kicker}>실제 돈 없이, 새로 들어오는 가격으로</p><h1>프로그램은 지금<br />어떤 판단을 하고 있나요?</h1><p>프로그램이 새 시세를 받아 보유할 종목과 금액을 계산하고, 가상으로 사고판 기록을 남기는 곳입니다. 실제 증권사 주문은 꺼져 있습니다.</p></section>
      <div className={styles.scope}><strong>앞에서 읽은 과거 시험과는 별도의 가상 계좌입니다.</strong><p>연구에서 수익이 높았던 설정이 이 계좌에 자동 적용되지 않습니다. 따라서 이곳의 기록을 앞선 연구 방식의 실제 성적으로 읽으면 안 됩니다.</p><details><summary>이 가상 계좌가 따르는 손실 대응 기준</summary><p>이 계좌는 장이 끝난 가격으로 계산한 금액이 기준 최고점에서 10% 떨어졌을 때 방어하도록 정한 모의 거래 규칙(PAPER)을 유지합니다. 현재 연구가 지향하는 20% 하락 목표와는 다릅니다. 실제 거래 가격은 달라질 수 있어 어느 수치도 손실을 보장해 막아 주지는 않습니다.</p></details></div>
      {(registrationError || !registration || !status || (registration.status !== "not_registered" && !identityMatches)) && <section className="notice" role="alert"><h2>{registrationProblem}</h2><p>{registrationError || !registration || !status ? "현재 계좌 상태 또는 사전에 등록한 검증 계획을 불러오지 못했습니다." : registration.status === "invalid_contract" ? "사전에 정한 검증 계획의 형식이 맞는지 확인하지 못했습니다." : "사전에 검증하기로 한 계좌·규칙과 현재 기록의 연결을 확인하지 못했습니다."} 아래 기록만으로 투자 방법이 검증됐다고 판단할 수 없습니다.</p><p><strong>지금 할 일:</strong> 이 기록으로 투자 여부를 결정하지 말고, <Link href="/research/progress">과거 연구 결과를 읽어 보세요</Link>. 운영자가 계좌와 검증 계획의 연결을 확인해야 합니다. 독자가 투자 설정을 바꿀 필요는 없으며, 이 안내가 해소된 뒤 검증 상태를 다시 확인하세요. 해결 예정 시각은 제공되지 않았습니다.</p></section>}
      {statusError || ledgerError ? (
        <section className="notice" role="alert"><h2>{statusError && ledgerError ? "모의 관찰 자료에 연결할 수 없습니다" : "모의 관찰 자료 일부를 읽을 수 없습니다"}</h2><p>{statusError ? "프로그램의 현재 상태를 확인할 수 없습니다." : "프로그램의 현재 상태는 확인되었습니다."} {ledgerError ? "현금·보유 종목·가상 거래 기록을 확인할 수 없습니다." : "가상 계좌의 기록은 확인되었습니다."}</p></section>
      ) : !status || !ledger ? (
        <section className="notice" role="status"><h2>모의 관찰 상태를 확인할 수 없습니다</h2><p>상태나 거래 기록이 제공되지 않았습니다. 정상 대기나 성과 없음으로 해석하지 않습니다.</p></section>
      ) : (
        <>
          <section className={styles.current} aria-labelledby="current-title"><p className={styles.kicker}>현재 자료에서 확인한 상태</p><h2 id="current-title">{stateLabel[status.session.state]}</h2><p>{stateMeaning[status.session.state] ?? "현재 상태의 쉬운 설명을 제공할 수 없습니다. 아래 기록에서 확인 가능한 내용만 읽어 주세요."}</p><p>먼저 최근 판단 시각을 확인하세요. 아래 예정 시각은 프로그램의 다음 계산 예정일이며, 독자가 주식을 사거나 팔아야 하는 날이 아닙니다.</p><dl><div><dt>최근 판단 기록</dt><dd>{status.latest_decision ? kst(status.latest_decision.recorded_at) : "기록 없음"}</dd></div><div><dt>계좌 평가 시각</dt><dd>{ledger.valuation_at ? kst(ledger.valuation_at) : "평가 시각 없음"}</dd></div><div><dt>다음 정기 판단 예정</dt><dd>{kst(status.session.next_due_at)}</dd></div><div><dt>별도 검증 등록 상태</dt><dd>{registrationLabel}</dd></div></dl></section>
          <section className="portfolio-metrics">
            <article className="metric-card"><span>가상 계좌에 남은 현금</span><strong>{researchAmount(ledger.cash_krw, 0)}원</strong><small>가상으로 시작한 돈 100,000,000원 · 실제 계좌 잔액 아님</small></article>
            <article className="metric-card"><span>시세 연결 상태</span><strong>{stateLabel[status.feed.state]}</strong><small>연결 상태만으로 검증 성공을 뜻하지 않습니다.</small></article>
            <article className="metric-card"><span>가상으로 사고판 기록</span><strong>{ledger.fills.length}건</strong><small>주식을 온전한 개수로, 주문 수량 전체가 거래됐다고 가정</small></article>
          </section>
          {status.blocked_reason && <section className="notice" role="status"><h2>판단에 필요한 자료에 문제가 있습니다</h2><p>이 상태에서는 정상적으로 관찰 중이라고 판단할 수 없습니다. 운영자가 아래 원인을 확인해야 하며, 독자가 거래 설정을 바꿀 필요는 없습니다.</p><details><summary>자료 문제의 상세 원인</summary><p>{status.blocked_reason}</p></details>{status.worker_failures.map((failure) => <p className="basis" key={failure.channel}>{failure.channel === "tick" ? "정기 워커" : "시세 워커"} · {failure.code} · {kst(failure.occurred_at)}</p>)}</section>}
          {status.preview.blocked_reason && status.preview.blocked_reason !== status.blocked_reason && <section className="notice" role="status"><h2>다음 판단을 계산할 자료를 사용할 수 없습니다</h2><p>다음 가상 거래가 가능하다는 뜻으로 읽지 마세요. 원인 확인은 운영자가 해야 합니다.</p><details><summary>자료 문제의 상세 원인</summary><p>{status.preview.blocked_reason}</p></details></section>}
          {!status.calendar.available && <section className="notice" role="alert"><h2>거래일 달력을 확인할 수 없습니다</h2><p>관련 가상 체결과 계좌 평가는 중단됩니다. 상세 오류는 달력 자료에서 확인하세요.</p></section>}
          {status.corporate_actions.some((action) => action.state === "blocked") && <section className="notice" role="alert"><h2>종목 분할 처리에 차단된 항목이 있습니다</h2><p>기업행동 상세에서 해당 종목과 차단 사유를 확인하세요.</p></section>}
          <div className={styles.sourceLinks}><Link href="/research/progress">과거 연구 결과와 비교하기 ↗</Link><a href={researchReportHref({ kind: "portfolio", id: status.session.source_run_id })}>이 모의 정책의 기준 보고서 읽기 ↗</a></div>
          <details className={styles.details}><summary>관찰 정책과 검증 기간 보기</summary><dl className="metric-list"><div><dt>정책 hash</dt><dd title={status.session.policy_hash}>{status.session.policy_hash.slice(0, 16)}…</dd></div><div><dt>활성화 시각</dt><dd>{kst(status.session.activated_at)}</dd></div><div><dt>검증 기간</dt><dd>{identityMatches && registered ? `${kst(registered.evaluation_start_at)} ~ ${kst(registered.evaluation_end_at)}` : "확인할 수 없음 · 위의 검증 계획 상태를 보세요"}</dd></div></dl></details>
          <details className={styles.details}><summary>컴퓨터 시계 진단 보기</summary><section className="panel research-step">
            <div className="section-title simple"><h2>호스트 시계 진단</h2><span className="status">{status.latest_clock_health?.state === "available" ? "측정값 확인" : "확인 불가"}</span></div>
            {!status.latest_clock_health ? <p className="empty-inline">앱 시작 직후 첫 진단을 기다리고 있습니다.</p> : <>
              <dl className="metric-list">
                <div><dt>시계 offset</dt><dd>{status.latest_clock_health.offset_ms === null ? "-" : `${status.latest_clock_health.offset_ms} ms`}</dd></div>
                <div><dt>network delay</dt><dd>{status.latest_clock_health.delay_ms === null ? "-" : `${status.latest_clock_health.delay_ms} ms`}</dd></div>
                <div><dt>jitter</dt><dd>{status.latest_clock_health.jitter_ms === null ? "-" : `${status.latest_clock_health.jitter_ms} ms`}</dd></div>
                <div><dt>packet count</dt><dd>{status.latest_clock_health.packet_count ?? "-"}</dd></div>
                <div><dt>명령 읽기 시각</dt><dd>{kst(status.latest_clock_health.sampled_at)}</dd></div>
                <div><dt>원장 보존</dt><dd>{status.latest_clock_health.persisted ? "저장됨" : `미저장 · ${status.latest_clock_health.error_code ?? "원인 미확인"}`}</dd></div>
              </dl>
              {status.latest_clock_health.state === "unknown" && <p className="notice" role="status">호스트 동기화 값을 확인할 수 없습니다. 제한 오류 코드: {status.latest_clock_health.error_code ?? "parse_error"}</p>}
            </>}
            <p className="basis">표시 시각은 `timedatectl timesync-status` 명령을 읽어 마친 UTC 시각이며 실제 NTP packet 측정 시각은 제공되지 않습니다. 이 진단 실패는 PAPER 워커 실패나 시세 적격성 변경으로 처리하지 않습니다.</p>
          </section></details>
          <details className={styles.details}><summary>종목별 시세 수신과 연결 진단 보기</summary><section className="panel research-step">
            <div className="section-title simple"><h2>16종목 단일 연결 관찰</h2><span className="status">{stateLabel[status.feed.state]}</span></div>
            <p>{status.feed.detail}</p>
            <div className="table-wrap"><table><thead><tr><th>종목</th><th>거래소</th><th>구독 단계</th><th>시세 상태</th><th>요청</th><th>전송 시작</th><th>승인 응답</th><th>첫 시세</th><th>시장 시각</th><th>수신 시각</th></tr></thead><tbody>{status.feed.items.map((item) => <tr key={item.symbol}><td>{item.symbol}</td><td>{item.exchange}</td><td>{item.ack_overdue ? "승인 확인 지연" : phaseLabel[item.subscription_phase]}</td><td>{feedState(item.state, item.subscription_phase, item.ack_overdue)}<br /><small>{item.detail}</small></td><td>{item.requested_at ? kst(item.requested_at) : "-"}</td><td>{item.sent_at ? kst(item.sent_at) : "-"}</td><td>{item.acknowledged_at ? kst(item.acknowledged_at) : "-"}</td><td>{item.first_quote_at ? kst(item.first_quote_at) : "-"}</td><td>{item.last_market_at ? kst(item.last_market_at) : "관측 대기"}</td><td>{item.last_received_at ? kst(item.last_received_at) : "-"}</td></tr>)}</tbody></table></div>
            <h3>프로토콜 진단</h3>
            <div className="table-wrap"><table><thead><tr><th>TR</th><th>데이터 프레임</th><th>유효 시세</th><th>검증 실패</th></tr></thead><tbody>{status.feed.protocol_counters.map((counter) => <tr key={counter.tr_id}><td>{counter.tr_id}</td><td>{counter.data_frame_count}</td><td>{counter.valid_quote_count}</td><td>{counter.parse_failure_count}</td></tr>)}</tbody></table></div>
            <p className="basis">출처: <a href={status.feed.provider_url}>{status.feed.provider}</a>. {status.feed.data_note}</p>
          </section></details>
          <details className={styles.details}><summary>거래일 달력과 출처 보기</summary><section className="panel research-step">
            <div className="section-title simple"><h2>고정 거래소 달력</h2><span className="status">{status.calendar.available ? "파일 검증됨" : "달력 차단"}</span></div>
            <p>전진 PAPER의 정규장 시세, 종가 평가, 분할 차단 시각은 같은 XKRX·XNYS 일정 파일을 사용합니다. 미국 NAS·NYS·AMS는 XNYS 공통 정규장 일정으로 판단합니다.</p>
            {!status.calendar.available && <div className="notice" role="alert"><strong>달력 파일을 확인할 수 없습니다.</strong><p>관련 가상 체결과 포트폴리오 평가는 중단됩니다. 오류 코드: {status.calendar.error_code ?? "calendar_unavailable"}</p></div>}
            <div className="table-wrap"><table><thead><tr><th>달력</th><th>현재 단계</th><th>현지 날짜</th><th>개장</th><th>폐장</th><th>다음 확인 세션</th></tr></thead><tbody>{status.calendar.exchanges.map((item) => <tr key={item.calendar}><td>{item.calendar}</td><td>{calendarPhaseLabel[item.phase]}</td><td>{item.local_date}</td><td>{item.open_at ? kst(item.open_at) : "-"}</td><td>{item.close_at ? kst(item.close_at) : "-"}</td><td>{item.next_session_open_at ? `${kst(item.next_session_open_at)} ~ ${item.next_session_close_at ? kst(item.next_session_close_at) : "-"}` : "지원 범위에서 확인되지 않음"}</td></tr>)}</tbody></table></div>
            <p className="basis">exchange_calendars {status.calendar.provider_version} · 지원 {status.calendar.coverage_start}~{status.calendar.coverage_end} · 파일 SHA-256 <span title={status.calendar.artifact_sha256}>{status.calendar.artifact_sha256.slice(0, 12)}…</span></p>
          </section></details>
          <details className={styles.details}><summary>주식 분할 등 기업행동 보기</summary><section className="panel research-step">
            <div className="section-title simple"><h2>검증된 기업행동</h2><span className="status">정수 정방향 분할만 지원</span></div>
            <p>운영자가 출처 문서와 SHA-256을 확인해 효력 거래일의 실제 개장 시각 전에 등록한 분할만 PAPER 원장에 반영합니다.</p>
            {status.corporate_actions.length === 0 ? <p className="empty-inline">등록된 검증 분할이 없습니다.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>비율</th><th>상태</th><th>관측</th><th>효력 개장</th><th>등록</th><th>적용</th><th>수량</th><th>증거</th></tr></thead><tbody>{status.corporate_actions.map((action) => <tr key={action.id}><td>{action.symbol}<br /><small>{action.exchange}</small></td><td>{action.factor}:1</td><td>{action.state === "applied" ? "반영됨" : action.state === "blocked" ? `차단 · ${action.blocked_reason}` : "등록됨"}</td><td>{kst(action.observed_at)}</td><td>{kst(action.effective_at)}</td><td>{kst(action.registered_at)}</td><td>{action.applied_at ? kst(action.applied_at) : "-"}</td><td>{action.before_quantity === null ? "-" : `${action.before_quantity} → ${action.after_quantity}`}</td><td><a href={action.source_url}>원문</a><br /><small title={action.evidence_sha256}>{action.evidence_id} · {action.evidence_sha256.slice(0, 12)}…</small></td></tr>)}</tbody></table></div>}
          </section></details>
          <details className={styles.details}><summary>가상 보유·체결 기록과 파일 내려받기</summary><section className="panel research-step">
            <h2>가상 원장</h2>
            <p className="basis">고정 정책 출처 <a href={researchReportHref({ kind: "portfolio", id: status.session.source_run_id })}>기준 연구 보고서 읽기</a></p>
            {ledger.positions.filter((item) => item.quantity > 0).length === 0 ? <p className="empty-inline">현재 보유한 종목이 없습니다. 다음 행동은 위 운용 상태와 판단 기록에서 확인하세요.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>수량</th><th>평균 원가</th></tr></thead><tbody>{ledger.positions.filter((item) => item.quantity > 0).map((item) => <tr key={item.symbol}><td>{item.symbol}</td><td>{item.quantity}</td><td>{researchAmount(item.average_cost_krw, 0)}원</td></tr>)}</tbody></table></div>}
            <h3>현재 preview (결정 아님)</h3><p>{Object.entries(status.preview.target_weights).map(([symbol, weight]) => `${symbol} ${researchAmount(String(Number(weight) * 100), 2)}%`).join(" · ") || "양의 목표 없음"}</p>
            <div className="artifact-links">{["observations.csv", "decisions.csv", "fills.csv", "events.csv", "equity.csv"].map((name) => <a key={name} href={`/research/forward/download/${name}`}>{name}</a>)}</div>
          </section></details>
          <section className={styles.limits}><h2>이 기록을 읽을 때 주의할 점</h2><p>가상 체결은 정수 수량을 한 번에 전량 체결했다고 가정합니다. 실제 체결과 다르며 배당 현금도 반영하지 않습니다. 모의 기록은 자동매매 승인 근거가 아닙니다.</p><details className={styles.details}><summary>모든 모의 관찰 한계 보기</summary><ul>{ledger.limitations.map((item) => <li key={item}>{item}</li>)}<li>배당 현금은 반영하지 않습니다.</li><li>검증된 정수 정방향 분할만 반영하며 역분할·소수 수량·현금 정산은 차단합니다.</li><li>과거 비교 엔진은 이번 고정 거래소 달력으로 변환하지 않았습니다.</li></ul><p>운용 예정 금액은 1억원, 사용자 허용 손실은 20%, 레버리지 상품 합산 상한은 20%입니다. 현재 PAPER 세션은 비교 가능성을 위해 더 엄격한 10% 종가 방어 기준을 유지합니다. 종가 원장 낙폭과 장중 경보는 구분하며, 10%는 평생 손실 보장이 아니고 이 결과는 자동매매 승인 근거가 아닙니다.</p></details></section>
        </>
      )}
    </main>
  );
}
