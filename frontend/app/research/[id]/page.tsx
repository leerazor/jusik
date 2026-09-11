import Link from "next/link";
import { notFound } from "next/navigation";
import { Refresh } from "@/app/refresh";
import {
  getResearchRun,
  getSymbolNames,
  researchAmount,
  researchRatePercent,
  researchSymbolLabel,
  type SymbolNames,
  type StrategyResult,
} from "@/lib/research";
import { replayResearchRun } from "../actions";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
};

function percent(value: string): string {
  return `${researchAmount(value, 2)}%`;
}

function StrategyCard({ title, data, symbolNames }: { title: string; data: StrategyResult; symbolNames: SymbolNames }) {
  return (
    <article className="strategy-card">
      <p className="eyebrow">{data.strategy_version}</p>
      <h2>{title}</h2>
      <p className="muted">{data.definition}</p>
      <dl className="metric-list">
        <div><dt>총수익률</dt><dd>{percent(data.metrics.total_return_pct)}</dd></div>
        <div><dt>최종 평가액</dt><dd>{researchAmount(data.metrics.final_equity, 0)}원</dd></div>
        <div><dt>최대 낙폭</dt><dd>{percent(data.metrics.max_drawdown_pct)}</dd></div>
        <div><dt>거래 수</dt><dd>{data.metrics.trade_count}건</dd></div>
        <div><dt>수수료</dt><dd>{researchAmount(data.metrics.total_fees, 0)}원</dd></div>
        <div><dt>매도 세금</dt><dd>{researchAmount(data.metrics.total_tax, 0)}원</dd></div>
        <div><dt>슬리피지 비용</dt><dd>{researchAmount(data.metrics.total_slippage_cost, 0)}원</dd></div>
      </dl>
      <p className="basis">
        종료 시점 보유: {Object.keys(data.open_positions).length > 0
          ? Object.entries(data.open_positions).map(([symbol, quantity]) => `${researchSymbolLabel(symbol, symbolNames)} ${quantity}주`).join(" · ")
          : "없음"}
      </p>
      <EquityLine data={data} />
    </article>
  );
}

function TradeTable({ data, symbolNames }: { data: StrategyResult; symbolNames: SymbolNames }) {
  const trades = [...data.trades].reverse();
  if (trades.length === 0) return <p className="empty-inline">체결된 거래가 없습니다.</p>;
  return (
    <div className="table-wrap"><table><thead><tr><th>종목</th><th>신호일 / 체결일</th><th>구분</th><th>수량</th><th>체결가</th><th>비용</th><th>근거</th></tr></thead><tbody>
      {trades.map((trade, index) => <tr key={`${trade.date}-${trade.symbol}-${index}`}><td>{researchSymbolLabel(trade.symbol, symbolNames)}</td><td>{trade.signal_date}<small>{trade.date}</small></td><td>{trade.side === "buy" ? "매수" : "매도"}</td><td>{trade.quantity}</td><td>{researchAmount(trade.execution_price, 0)}원</td><td>{researchAmount(trade.fee, 0)}원<small>세금 {researchAmount(trade.tax, 0)}원</small></td><td className="reason-cell">{trade.rationale}</td></tr>)}
    </tbody></table></div>
  );
}

function EquityLine({ data }: { data: StrategyResult }) {
  if (data.equity.length < 2) return null;
  const values = data.equity.map((item) => Number(item.equity));
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100;
    const y = 36 - ((value - min) / range) * 32;
    return `${x},${y}`;
  }).join(" ");
  return <svg className="equity-line" viewBox="0 0 100 40" role="img" aria-label="평가액 흐름"><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg>;
}

export default async function ResearchRunPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const query = await searchParams;
  let run;
  let symbolNames: SymbolNames = {};
  let unavailable = false;
  try {
    run = await getResearchRun(id);
  } catch {
    unavailable = true;
  }
  try {
    symbolNames = await getSymbolNames();
  } catch {
    symbolNames = {};
  }
  if (unavailable) {
    return (
      <main>
        <header><Link href="/research" className="brand"><span className="mark">J</span> jusik</Link><Link href="/research" className="secondary-button">검증 결과 목록</Link></header>
        <section className="notice" role="alert"><h2>연구 백엔드에 연결할 수 없습니다</h2><p>서비스 실행 상태를 확인한 뒤 다시 시도하세요.</p></section>
      </main>
    );
  }
  if (!run) notFound();
  const result = run.result;
  const active = ["queued", "collecting", "running"].includes(run.status);

  return (
    <main>
      <header className="research-result-header">
        <Link href="/research" className="brand">
          <span className="mark">J</span> jusik
          <span className="brand-sub">백테스트 결과</span>
        </Link>
        <div className="action-row">
          <Link className="secondary-button" href="/research">검증 결과 목록</Link>
          <a className="secondary-button" href="/research-guide.html">사용 안내 보기</a>
          <span className="badge">연구 전용 · 실전 반영 불가</span>
        </div>
      </header>
      <section className="intro research-intro">
        <div>
          <p className="eyebrow">RUN {run.id.slice(0, 8)}</p>
          <h1>백테스트 결과</h1>
          <p className="muted">{run.request.start_date}–{run.request.end_date} · {run.request.symbols.map((symbol) => researchSymbolLabel(symbol, symbolNames)).join(" · ")}</p>
        </div>
        <div className="action-row">
          <Refresh />
          {run.input_hash && (
            <form action={replayResearchRun}>
              <input type="hidden" name="id" value={run.id} />
              <button type="submit" className="secondary-button">저장된 데이터로 다시 검증</button>
            </form>
          )}
        </div>
      </section>
      {run.input_hash && <p className="basis replay-note">다시 검증은 저장된 입력과 일봉을 사용하며 새 시세를 받지 않습니다.</p>}

      {query.error && <section className="notice" role="alert"><h2>재생을 시작하지 못했습니다</h2></section>}
      {run.error && <section className="notice" role="alert"><h2>{run.status === "insufficient" ? "검증 불충분" : "연구 실패"}</h2><p>{run.error}</p></section>}
      {result?.coverage_status === "common_sessions_unverified" && (
        <section className="notice quality-warning" role="status">
          <h2>계산 완료 · 공통 거래일 검증 전</h2>
          <p>공식 KRX 거래일 달력이 없어 모든 종목에서 동시에 빠진 일봉은 확인하지 못했습니다. 아래 수치는 수집된 일봉에 대한 계산 결과입니다.</p>
        </section>
      )}

      {!result && active ? (
        <section className="panel pending-panel">
          <h2>{run.status === "queued" ? "실행 대기 중" : run.status === "collecting" ? "모의 시세 수집 중" : "검증 계산 중"}</h2>
          <p className="muted">이 페이지를 새로고침하면 최신 상태를 확인할 수 있습니다.</p>
        </section>
      ) : result ? (
        <>
          <section className="strategy-grid">
            <StrategyCard title="기준 전략 · 20일 추세" data={result.baseline} symbolNames={symbolNames} />
            <StrategyCard title="후보 전략 · 20/60일 추세" data={result.candidate} symbolNames={symbolNames} />
          </section>

          {result.validation && <section className="panel research-section">
            <div className="section-title simple"><h2>시간순 평가</h2><span className="muted">첫 실행의 후반 구간 · 반복 연구 시 재사용 가능</span></div>
            <p><strong>{result.validation.testing_start}–{result.validation.testing_end}</strong> · 추천 {result.validation.recommended_version}</p>
            <div className="metric-list">
              <div><dt>기준 수익률</dt><dd>{percent(result.validation.baseline.total_return_pct)}</dd></div>
              <div><dt>후보 수익률</dt><dd>{percent(result.validation.candidate.total_return_pct)}</dd></div>
              <div><dt>기준 최대 낙폭</dt><dd>{percent(result.validation.baseline.max_drawdown_pct)}</dd></div>
              <div><dt>후보 최대 낙폭</dt><dd>{percent(result.validation.candidate.max_drawdown_pct)}</dd></div>
            </div>
            <p className="basis">{result.validation.reason} 자동으로 운영 전략을 바꾸지는 않습니다.</p>
          </section>}

          <section className="panel research-section">
            <div className="section-title simple"><h2>데이터 범위</h2><span className="muted">시장 이벤트 {result.event_coverage === "unavailable" ? "확인 불가" : "사용자 제공분만 반영"}</span></div>
            <div className="table-wrap"><table><thead><tr><th>종목</th><th>비교 범위</th><th>일봉</th><th>준비 구간</th><th>다른 종목 대비 누락</th><th>기대 거래일 대비 누락</th></tr></thead><tbody>
              {result.coverage.map((item) => <tr key={item.symbol}><td>{researchSymbolLabel(item.symbol, symbolNames)}</td><td>{item.first_date}–{item.last_date}</td><td>{item.bars}</td><td>{item.warmup_bars}</td><td>{item.missing_vs_union_dates}</td><td>{item.missing_expected_sessions ?? "확인 불가"}</td></tr>)}
            </tbody></table></div>
          </section>

          <section className="panel research-section assumptions">
            <div className="section-title simple"><h2>검증 가정</h2><span className="muted">저장된 요청값</span></div>
            <dl className="metric-list">
              <div><dt>초기 현금</dt><dd>{researchAmount(run.request.initial_cash, 0)}원</dd></div>
              <div><dt>매매 수수료율</dt><dd>{researchRatePercent(run.request.fee_rate)}</dd></div>
              <div><dt>슬리피지율</dt><dd>{researchRatePercent(run.request.slippage_rate)}</dd></div>
              <div><dt>매도 세율</dt><dd>{researchRatePercent(run.request.sell_tax_rate)}</dd></div>
            </dl>
          </section>

          <section className="panel research-section">
            <div className="section-title simple"><h2>기준 전략 모의 거래 내역</h2><span className="muted">최근 체결부터 표시</span></div>
            <TradeTable data={result.baseline} symbolNames={symbolNames} />
          </section>

          <section className="panel research-section">
            <div className="section-title simple"><h2>후보 전략 모의 거래 내역</h2><span className="muted">최근 체결부터 표시</span></div>
            <TradeTable data={result.candidate} symbolNames={symbolNames} />
          </section>

          {([[
            "기준 전략 지연·미체결",
            result.baseline,
          ], [
            "후보 전략 지연·미체결",
            result.candidate,
          ]] as const).map(([title, strategy]) =>
            (strategy.affected_decisions.length > 0 || strategy.unfilled_decisions.length > 0) && (
              <section className="panel research-section" key={title}><div className="section-title simple"><h2>{title}</h2></div>
                {strategy.affected_decisions.map((item) => <p className="decision-row" key={`${item.date}-${item.symbol}-${item.source_url}`}>{item.date} · {researchSymbolLabel(item.symbol, symbolNames)} · {item.reason} <a href={item.source_url} target="_blank" rel="noreferrer">출처</a></p>)}
                {strategy.unfilled_decisions.map((item, index) => <p className="decision-row" key={`${item.date}-${item.symbol}-${index}`}>{item.date} · {researchSymbolLabel(item.symbol, symbolNames)} · {item.reason}</p>)}
              </section>
            ),
          )}

          <section className="panel research-section limitations"><div className="section-title simple"><h2>해석 한계</h2></div><ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
          <section className="hashes"><p>엔진 {result.engine_version}</p><p>입력 SHA-256 {result.input_hash}</p><p>조건 SHA-256 {result.parameters_hash}</p><p>구현 SHA-256 {result.implementation_hash ?? "기존 기록 · 확인 불가"}</p>{run.replay_of && <p>재생 원본 {run.replay_of}</p>}</section>
        </>
      ) : null}
    </main>
  );
}
