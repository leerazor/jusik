import Link from "next/link";
import {
  getOperationsStatus,
  getResearchRuns,
  getSymbolNames,
  researchAmount,
  researchSymbolLabel,
  type SymbolNames,
} from "@/lib/research";
import {
  activatePaperStrategy,
  createResearchRun,
  decideProposal,
  runScheduledNow,
  toggleStream,
  updateSchedule,
  updateUniverse,
} from "./actions";
import { OperationsRefresh } from "./operations-refresh";

export const dynamic = "force-dynamic";

const statusLabels = {
  queued: "대기",
  collecting: "데이터 수집",
  running: "검증 중",
  completed: "완료",
  insufficient: "검증 불충분",
  failed: "실패",
} as const;

const streamLabels = {
  disabled: "꺼짐",
  connecting: "연결 중",
  connected: "연결됨",
  stale: "지연",
  error: "오류",
} as const;

type PageProps = {
  searchParams: Promise<{ error?: string }>;
};

export default async function ResearchPage({ searchParams }: PageProps) {
  const query = await searchParams;
  let runs = null;
  let operations = null;
  let symbolNames: SymbolNames = {};
  try {
    runs = await getResearchRuns();
  } catch {
    runs = null;
  }
  try {
    operations = await getOperationsStatus();
  } catch {
    operations = null;
  }
  try {
    symbolNames = await getSymbolNames();
  } catch {
    symbolNames = {};
  }

  return (
    <main>
      <header>
        <Link href="/" className="brand">
          <span className="mark">J</span> jusik
          <span className="brand-sub">전략 연구</span>
        </Link>
        <span className="badge">과거 시세 · 모의 체결</span>
      </header>

      <section className="intro research-intro">
        <div>
          <p className="eyebrow">PAPER RESEARCH</p>
          <h1>같은 데이터로 전략을 비교합니다.</h1>
          <p className="muted">
            선택한 1~10개 국내 종목에서 일봉 추세·거래량 전략을 같은 비용과
            독립 평가 자금으로 검증하고, 승인한 paper 체결만 기록합니다.
          </p>
        </div>
        <div className="action-row">
          <a className="secondary-button" href="/research-guide.html">사용 안내</a>
          <Link className="secondary-button" href="/">계좌 현황</Link>
        </div>
      </section>
      {operations && <OperationsRefresh />}

      {operations ? (
        <>
          <section className="operations-overview">
            <article className="hero-card">
              <span>Paper 가용 현금</span>
              <strong>{researchAmount(operations.paper_account.cash, 0)}원</strong>
              <small>앱 내부 모의 원장 · 실제 주문 없음</small>
            </article>
            <article className="metric-card">
              <span>실시간 시세</span>
              <strong className="compact-value">{streamLabels[operations.stream.state]}</strong>
              <small>{operations.stream.detail}</small>
            </article>
            <article className="metric-card">
              <span>승인 대기</span>
              <strong>{operations.proposals.filter((item) => item.status === "pending").length}건</strong>
              <small>10초마다 상태 갱신</small>
            </article>
          </section>

          <section className="operations-grid">
            <article className="panel operation-card">
              <div className="section-title simple"><h2>연구 대상과 주기</h2></div>
              <form action={updateUniverse} className="inline-form">
                <label>국내 종목 코드
                  <input name="symbols" defaultValue={operations.universe.join(", ")} required inputMode="numeric" />
                  <small>현재 대상: {operations.universe.map((symbol) => researchSymbolLabel(symbol, symbolNames)).join(" · ")}</small>
                </label>
                <button type="submit">대상 저장</button>
              </form>
              <form action={updateSchedule} className="schedule-form">
                <label className="check-label"><input type="checkbox" name="enabled" defaultChecked={operations.schedule.enabled} /> 정기 연구 사용</label>
                <label>실행 간격(시간)<input name="interval_hours" type="number" min="1" max="168" defaultValue={operations.schedule.interval_hours} /></label>
                <label>검증 기간(일)<input name="lookback_days" type="number" min="120" max="1096" defaultValue={operations.schedule.lookback_days} /></label>
                <button type="submit">일정 저장</button>
              </form>
              <form action={runScheduledNow}><button type="submit" className="secondary-button">현재 설정으로 지금 실행</button></form>
              <p className="basis">다음 예정 {new Date(operations.schedule.next_run_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST</p>
              <p className="basis">최근 실행 {operations.schedule.last_run_id?.slice(0, 8) ?? "없음"}{operations.schedule.last_error ? ` · ${operations.schedule.last_error}` : ""}</p>
            </article>

            <article className="panel operation-card">
              <div className="section-title simple"><h2>실시간 시세 연결</h2><span className={`status status-${operations.stream.state}`}>{streamLabels[operations.stream.state]}</span></div>
              <p>{operations.stream.detail}</p>
              <p className="basis">H0STCNT0 체결가 · 읽기 전용 · {operations.quotes.length}개 최신 시세</p>
              <form action={toggleStream}>
                <input type="hidden" name="enabled" value={operations.stream.state === "disabled" ? "true" : "false"} />
                <button type="submit">{operations.stream.state === "disabled" ? "연결 켜기" : "연결 끄기"}</button>
              </form>
              <div className="quote-list">
                {operations.quotes.map((quote) => <p key={quote.symbol}><strong>{researchSymbolLabel(quote.symbol, symbolNames)}</strong><span>{researchAmount(quote.price, 0)}원<small>{new Date(quote.market_at).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 수신 {new Date(quote.received_at).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })}</small></span></p>)}
              </div>
            </article>

            <article className="panel operation-card">
              <div className="section-title simple"><h2>OpenAI 연구 검토</h2></div>
              <p>{operations.ai.enabled ? "사용 중" : operations.ai.configured ? "예산 0 · 꺼짐" : "API 설정 없음 · 꺼짐"}</p>
              <p className="basis">모델 {operations.ai.model ?? "미설정"} · 오늘 보수적 예약 {operations.ai.used_tokens_today}/{operations.ai.daily_token_budget} tokens</p>
              {operations.ai.last_analysis && <p>{operations.ai.last_analysis}</p>}
              {operations.ai.last_error && <p className="basis">최근 오류: {operations.ai.last_error}</p>}
              <p className="basis">AI는 제한된 후보만 제안하며 합격 판정과 체결을 수행하지 않습니다.</p>
            </article>
          </section>

          <section className="panel research-section">
            <div className="section-title simple"><h2>전략 버전</h2><span className="muted">내장 전략은 반복 구간 · AI 후보는 생성 후 1회</span></div>
            <div className="strategy-version-grid">
              {operations.versions.map((item) => (
                <article key={item.definition.version} className={item.active_for_paper ? "selected-version" : ""}>
                  <strong>{item.definition.name}</strong>
                  <small>{item.definition.version}</small>
                  <p>{item.definition.definition}</p>
                  <p className="basis">평가 수익률 {item.out_of_sample_return_pct === null ? "대기" : `${researchAmount(item.out_of_sample_return_pct)}%`} · 낙폭 {item.out_of_sample_max_drawdown_pct === null ? "대기" : `${researchAmount(item.out_of_sample_max_drawdown_pct)}%`}</p>
                  <p className="basis">평가 구간 {item.evaluation_start && item.evaluation_end ? `${item.evaluation_start}–${item.evaluation_end}` : "대기"}{item.proposed_after_date ? ` · 제안 후 ${item.proposed_after_date} 이후만 사용` : " · 사전 정의 전략"}</p>
                  <p className="basis">{item.recommended ? "추천 후보 · " : ""}{item.reason}</p>
                  <form action={activatePaperStrategy}>
                    <input type="hidden" name="version" value={item.definition.version} />
                    <button type="submit" disabled={item.active_for_paper || (item.source === "openai_suggestion" && item.passed !== true)}>{item.active_for_paper ? "Paper 운영 중" : "Paper 전략으로 선택"}</button>
                  </form>
                </article>
              ))}
            </div>
          </section>

          <section className="panel research-section">
            <div className="section-title simple"><h2>신호 승인</h2><span className="muted">매수·매도 모두 승인 필요</span></div>
            <div className="proposal-list">
              {operations.proposals.length === 0 && <p className="empty-inline">아직 생성된 제안이 없습니다.</p>}
              {operations.proposals.slice(0, 20).map((proposal) => (
                <article key={proposal.id}>
                  <div><strong>{proposal.side === "buy" ? "매수" : "매도"} · {researchSymbolLabel(proposal.symbol, symbolNames)}</strong><span className={`status status-${proposal.status}`}>{proposal.status}</span></div>
                  <p>{proposal.quantity}주 · 가격 한도 {researchAmount(proposal.limit_price, 0)}원</p>
                  <p className="basis">{proposal.strategy_version} · {proposal.signal_date} 확정 일봉 · {new Date(proposal.expires_at).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })} KST 만료</p>
                  <p className="basis">{proposal.reason}</p>
                  {proposal.status === "pending" && <div className="action-row">
                    <form action={decideProposal}><input type="hidden" name="id" value={proposal.id} /><input type="hidden" name="version" value={proposal.strategy_version} /><input type="hidden" name="action" value="approve" /><button type="submit">Paper 체결 승인</button></form>
                    <form action={decideProposal}><input type="hidden" name="id" value={proposal.id} /><input type="hidden" name="version" value={proposal.strategy_version} /><input type="hidden" name="action" value="reject" /><button type="submit" className="secondary-button">거절</button></form>
                  </div>}
                </article>
              ))}
            </div>
          </section>

          <section className="panel research-section">
            <div className="section-title simple"><h2>Paper 포지션과 체결</h2><span className="muted">재시작 후에도 보존</span></div>
            <p>{Object.keys(operations.paper_account.positions).length === 0 ? "보유 포지션 없음" : Object.entries(operations.paper_account.positions).map(([symbol, quantity]) => `${researchSymbolLabel(symbol, symbolNames)} ${quantity}주`).join(" · ")}</p>
            <div className="fill-list">
              {operations.paper_account.fills.length === 0 && <p className="empty-inline">아직 paper 체결이 없습니다.</p>}
              {operations.paper_account.fills.slice(0, 20).map((fill) => <p key={fill.id}><strong>{fill.side === "buy" ? "매수" : "매도"} · {researchSymbolLabel(fill.symbol, symbolNames)}</strong><span>{fill.quantity}주 · {researchAmount(fill.price, 0)}원 · 수수료 {researchAmount(fill.fee, 0)}원 · 세금 {researchAmount(fill.tax, 0)}원</span><small>{new Date(fill.filled_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 앱 모의 체결</small></p>)}
            </div>
          </section>

          {operations.warnings.map((warning) => <p className="basis operation-warning" key={warning}>{warning}</p>)}
        </>
      ) : <section className="notice" role="alert"><h2>운영 상태를 불러오지 못했습니다</h2><p>연구 백엔드 8001 포트를 확인하세요.</p></section>}

      {query.error && (
        <section role="alert" className="notice">
          <h2>연구 요청을 시작하지 못했습니다</h2>
          <p>
            {query.error === "event-json"
              ? "시장 이벤트 JSON 배열의 형식을 확인하세요."
              : "연구 백엔드 상태와 입력값을 확인하세요."}
          </p>
        </section>
      )}
      {runs?.some((run) => run.result?.coverage_status === "common_sessions_unverified") && (
        <section role="status" className="notice quality-warning">
          <h2>공통 거래일 범위는 아직 검증되지 않았습니다</h2>
          <p>공식 KRX 거래일 달력을 연결하기 전까지 모든 종목에서 함께 빠진 일봉은 탐지할 수 없습니다.</p>
        </section>
      )}

      <section className="research-layout">
        <form action={createResearchRun} className="panel research-form">
          <div className="section-title simple">
            <h2>새 백테스트</h2>
            <span className="muted">최대 3년 · 최대 10종목</span>
          </div>
          <label>
            종목 코드
            <input name="symbols" defaultValue={operations?.universe.join(", ") ?? "005930, 000660"} inputMode="numeric" required />
            <small>6자리 국내 종목 코드를 쉼표로 구분합니다.</small>
          </label>
          <div className="form-grid">
            <label>
              시작일
              <input name="start_date" type="date" defaultValue="2025-01-02" required />
            </label>
            <label>
              종료일
              <input name="end_date" type="date" defaultValue="2025-06-30" required />
            </label>
            <label>
              초기 현금 (원)
              <input name="initial_cash" defaultValue="100000000" inputMode="decimal" required />
            </label>
            <label>
              매매 수수료율 (0.001 = 0.1%)
              <input name="fee_rate" defaultValue="0.00015" inputMode="decimal" required />
            </label>
            <label>
              슬리피지율 (0.001 = 0.1%)
              <input name="slippage_rate" defaultValue="0.001" inputMode="decimal" required />
            </label>
            <label>
              매도 세율 (0.001 = 0.1%)
              <input name="sell_tax_rate" defaultValue="0.0018" inputMode="decimal" required />
            </label>
          </div>
          <details>
            <summary>출처가 있는 시장 이벤트 입력</summary>
            <label>
              이벤트 JSON 배열
              <textarea
                name="events"
                rows={7}
                placeholder={'[{"kind":"sidecar","market":"KOSPI","direction":"down","stage":null,"occurred_at":"2025-04-07T09:12:00+09:00","known_at":"2025-04-07T09:13:00+09:00","resumed_at":"2025-04-07T09:17:00+09:00","source_url":"https://..."}]'}
              />
              <small>
                아래 내용은 형식 예시이며 실제 발동 기록이 아닙니다.
                `occurred_at`, `known_at`, `resumed_at`과 원문 URL을 함께 넣습니다.
                입력하지 않으면 이벤트 범위는 확인 불가로 표시됩니다.
              </small>
            </label>
          </details>
          <button type="submit">연구 실행</button>
          <p className="basis">
            KIS 모의투자 일봉만 조회합니다. 이 화면은 주문을 만들거나 전략을
            실전에 반영하지 않습니다. 비용 기본값도 검증 가정이며 실제 적용
            수수료·세금과 대조해야 합니다.
          </p>
        </form>

        <section className="panel" aria-labelledby="run-list-title">
          <div className="section-title simple">
            <h2 id="run-list-title">최근 실행</h2>
            <span className="muted">저장된 실행</span>
          </div>
          {runs === null ? (
            <p className="empty-inline">연구 백엔드에 연결할 수 없습니다.</p>
          ) : runs.length === 0 ? (
            <p className="empty-inline">아직 실행 기록이 없습니다.</p>
          ) : (
            <div className="run-list">
              {runs.map((run) => (
                <Link href={`/research/${run.id}`} key={run.id} className="run-row">
                  <span>
                    <strong>{run.request.start_date}–{run.request.end_date}</strong>
                    <small>{run.request.symbols.map((symbol) => researchSymbolLabel(symbol, symbolNames)).join(" · ")}</small>
                  </span>
                  <span className={`status status-${run.status}`}>
                    {statusLabels[run.status]}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
