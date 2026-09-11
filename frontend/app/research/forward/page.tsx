import Link from "next/link";
import { getForwardLedger, getForwardStatus, researchAmount } from "@/lib/research";

export const dynamic = "force-dynamic";

function kst(value: string): string {
  return `${new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}
const stateLabel: Record<string, string> = {
  observing: "관찰 중", waiting_cadence: "정기 판단 대기", decision_recorded: "결정 기록",
  awaiting_quotes: "유효 시세 대기", completed: "완료", partially_completed: "일부 체결",
  expired: "만료", inputs_blocked: "입력 차단", risk_liquidation: "위험 청산",
  cooldown: "재진입 대기", recovery_wait: "회복 확인", reentry_ready: "재진입 준비",
  disabled: "비활성", connecting: "연결 중", connected: "수신 중", partial: "일부 수신",
  stale: "시세 지연", error: "오류", pending: "첫 시세 대기", rejected: "구독 거부",
  unsupported: "미지원",
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

export default async function ForwardResearchPage() {
  let status = null;
  let ledger = null;
  try {
    [status, ledger] = await Promise.all([getForwardStatus(), getForwardLedger()]);
  } catch {
    status = null;
  }
  return (
    <main>
      <header className="research-result-header">
        <Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">전진 PAPER</span></Link>
        <div className="action-row"><Link className="secondary-button" href="/research/validation">검증 증거</Link><Link className="secondary-button" href="/research/actions">기업행동 관측</Link><Link className="secondary-button" href="/research/history">개발 이력</Link><Link className="secondary-button" href="/research/portfolio">과거 비교</Link></div>
      </header>
      <section className="intro research-intro">
        <div><p className="eyebrow">FORWARD PAPER OBSERVATION</p><h1>새 시세부터 쌓는 전진 관찰</h1><p className="muted">활성화 이전 손익과 보유는 가져오지 않았습니다. 사전 고정한 저회전 결합 정책을 1억원 현금 원장에서 관찰하며 실제 주문은 만들지 않습니다.</p></div>
        <span className="badge">브로커 주문 꺼짐</span>
      </section>
      {!status || !ledger ? (
        <section className="notice" role="alert"><h2>전진 관찰 상태를 읽을 수 없습니다</h2><p>연구 백엔드 연결과 저장소 상태를 확인하세요.</p></section>
      ) : (
        <>
          <section className="portfolio-metrics">
            <article className="metric-card"><span>PAPER 현금</span><strong>{researchAmount(ledger.cash_krw, 0)}원</strong><small>초기 100,000,000원 · 과거 seed 없음</small></article>
            <article className="metric-card"><span>현재 상태</span><strong>{stateLabel[status.session.state]}</strong><small>다음 정기 시각 {kst(status.session.next_due_at)}</small></article>
            <article className="metric-card"><span>가상 체결</span><strong>{ledger.fills.length}건</strong><small>정수 수량 전량 체결 가정</small></article>
          </section>
          {status.blocked_reason && <section className="notice" role="status"><h2>현재 입력 차단</h2><p>{status.blocked_reason}</p>{status.worker_failures.map((failure) => <p className="basis" key={failure.channel}>{failure.channel === "tick" ? "정기 워커" : "시세 워커"} · {failure.code} · {kst(failure.occurred_at)}</p>)}</section>}
          <section className="panel research-step">
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
          </section>
          <section className="panel research-step">
            <div className="section-title simple"><h2>16종목 단일 연결 관찰</h2><span className="status">{stateLabel[status.feed.state]}</span></div>
            <p>{status.feed.detail}</p>
            <div className="table-wrap"><table><thead><tr><th>종목</th><th>거래소</th><th>구독 단계</th><th>시세 상태</th><th>요청</th><th>전송 시작</th><th>승인 응답</th><th>첫 시세</th><th>시장 시각</th><th>수신 시각</th></tr></thead><tbody>{status.feed.items.map((item) => <tr key={item.symbol}><td>{item.symbol}</td><td>{item.exchange}</td><td>{item.ack_overdue ? "승인 확인 지연" : phaseLabel[item.subscription_phase]}</td><td>{feedState(item.state, item.subscription_phase, item.ack_overdue)}<br /><small>{item.detail}</small></td><td>{item.requested_at ? kst(item.requested_at) : "-"}</td><td>{item.sent_at ? kst(item.sent_at) : "-"}</td><td>{item.acknowledged_at ? kst(item.acknowledged_at) : "-"}</td><td>{item.first_quote_at ? kst(item.first_quote_at) : "-"}</td><td>{item.last_market_at ? kst(item.last_market_at) : "관측 대기"}</td><td>{item.last_received_at ? kst(item.last_received_at) : "-"}</td></tr>)}</tbody></table></div>
            <h3>프로토콜 진단</h3>
            <div className="table-wrap"><table><thead><tr><th>TR</th><th>데이터 프레임</th><th>유효 시세</th><th>검증 실패</th></tr></thead><tbody>{status.feed.protocol_counters.map((counter) => <tr key={counter.tr_id}><td>{counter.tr_id}</td><td>{counter.data_frame_count}</td><td>{counter.valid_quote_count}</td><td>{counter.parse_failure_count}</td></tr>)}</tbody></table></div>
            <p className="basis">출처: <a href={status.feed.provider_url}>{status.feed.provider}</a>. {status.feed.data_note}</p>
          </section>
          <section className="panel research-step">
            <div className="section-title simple"><h2>고정 거래소 달력</h2><span className="status">{status.calendar.available ? "파일 검증됨" : "달력 차단"}</span></div>
            <p>전진 PAPER의 정규장 시세, 종가 평가, 분할 차단 시각은 같은 XKRX·XNYS 일정 파일을 사용합니다. 미국 NAS·NYS·AMS는 XNYS 공통 정규장 일정으로 판단합니다.</p>
            {!status.calendar.available && <div className="notice" role="alert"><strong>달력 파일을 확인할 수 없습니다.</strong><p>관련 가상 체결과 포트폴리오 평가는 중단됩니다. 오류 코드: {status.calendar.error_code ?? "calendar_unavailable"}</p></div>}
            <div className="table-wrap"><table><thead><tr><th>달력</th><th>현재 단계</th><th>현지 날짜</th><th>개장</th><th>폐장</th><th>다음 확인 세션</th></tr></thead><tbody>{status.calendar.exchanges.map((item) => <tr key={item.calendar}><td>{item.calendar}</td><td>{calendarPhaseLabel[item.phase]}</td><td>{item.local_date}</td><td>{item.open_at ? kst(item.open_at) : "-"}</td><td>{item.close_at ? kst(item.close_at) : "-"}</td><td>{item.next_session_open_at ? `${kst(item.next_session_open_at)} ~ ${item.next_session_close_at ? kst(item.next_session_close_at) : "-"}` : "지원 범위에서 확인되지 않음"}</td></tr>)}</tbody></table></div>
            <p className="basis">exchange_calendars {status.calendar.provider_version} · 지원 {status.calendar.coverage_start}~{status.calendar.coverage_end} · 파일 SHA-256 <span title={status.calendar.artifact_sha256}>{status.calendar.artifact_sha256.slice(0, 12)}…</span></p>
          </section>
          <section className="panel research-step">
            <div className="section-title simple"><h2>검증된 기업행동</h2><span className="status">정수 정방향 분할만 지원</span></div>
            <p>운영자가 출처 문서와 SHA-256을 확인해 효력 거래일의 실제 개장 시각 전에 등록한 분할만 PAPER 원장에 반영합니다.</p>
            {status.corporate_actions.length === 0 ? <p className="empty-inline">등록된 검증 분할이 없습니다.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>비율</th><th>상태</th><th>관측</th><th>효력 개장</th><th>등록</th><th>적용</th><th>수량</th><th>증거</th></tr></thead><tbody>{status.corporate_actions.map((action) => <tr key={action.id}><td>{action.symbol}<br /><small>{action.exchange}</small></td><td>{action.factor}:1</td><td>{action.state === "applied" ? "반영됨" : action.state === "blocked" ? `차단 · ${action.blocked_reason}` : "등록됨"}</td><td>{kst(action.observed_at)}</td><td>{kst(action.effective_at)}</td><td>{kst(action.registered_at)}</td><td>{action.applied_at ? kst(action.applied_at) : "-"}</td><td>{action.before_quantity === null ? "-" : `${action.before_quantity} → ${action.after_quantity}`}</td><td><a href={action.source_url}>원문</a><br /><small title={action.evidence_sha256}>{action.evidence_id} · {action.evidence_sha256.slice(0, 12)}…</small></td></tr>)}</tbody></table></div>}
          </section>
          <section className="panel research-step">
            <h2>가상 원장</h2>
            <p className="basis">고정 정책 출처 <a href={`/research/portfolio/download/${status.session.source_run_id}/report.md`}>기준 연구 보고서</a></p>
            {ledger.positions.filter((item) => item.quantity > 0).length === 0 ? <p className="empty-inline">현재 보유 없음. 첫 정기 결정 또는 유효 시세를 기다립니다.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>수량</th><th>평균 원가</th></tr></thead><tbody>{ledger.positions.filter((item) => item.quantity > 0).map((item) => <tr key={item.symbol}><td>{item.symbol}</td><td>{item.quantity}</td><td>{researchAmount(item.average_cost_krw, 0)}원</td></tr>)}</tbody></table></div>}
            <h3>현재 preview (결정 아님)</h3><p>{Object.entries(status.preview.target_weights).map(([symbol, weight]) => `${symbol} ${researchAmount(String(Number(weight) * 100), 2)}%`).join(" · ") || "양의 목표 없음"}</p>
            <div className="artifact-links">{["observations.csv", "decisions.csv", "fills.csv", "events.csv", "equity.csv"].map((name) => <a key={name} href={`/research/forward/download/${name}`}>{name}</a>)}</div>
          </section>
          <section className="notice quality-warning"><h2>전진 PAPER의 범위</h2><ul>{ledger.limitations.map((item) => <li key={item}>{item}</li>)}<li>배당 현금은 반영하지 않습니다.</li><li>검증된 정수 정방향 분할만 반영하며 역분할·소수 수량·현금 정산은 차단합니다.</li><li>과거 비교 엔진은 이번 고정 거래소 달력으로 변환하지 않았습니다.</li></ul><p>운용 예정 금액은 1억원, 사용자 허용 손실은 20%, 레버리지 상품 합산 상한은 20%입니다. 현재 PAPER 세션은 비교 가능성을 위해 더 엄격한 10% 종가 방어 기준을 유지합니다. 종가 원장 낙폭과 장중 경보는 구분하며, 10%는 평생 손실 보장이 아니고 이 결과는 자동매매 승인 근거가 아닙니다.</p></section>
        </>
      )}
    </main>
  );
}
