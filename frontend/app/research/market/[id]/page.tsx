import Link from "next/link";
import { getMarketResearchRun, marketAmount, marketResearchNullResultMessage, marketResearchRunLabel, marketResearchSourceLabel, type MarketResearchRun } from "@/lib/marketResearch";

export const dynamic = "force-dynamic";

function metric(run: MarketResearchRun, key: string): string {
  const value = run.result?.metrics[key];
  return value !== undefined ? marketAmount(value) : "확인 불가";
}

function stageLabel(stage: MarketResearchRun["stage"]): string {
  return { pilot: "1년 파일럿", final: "3년 최종", legacy: "기존 실행" }[stage];
}

export default async function MarketResearchDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let run: MarketResearchRun;
  try { run = await getMarketResearchRun(id); } catch { return <main><section className="notice" role="alert"><h2>시장 연구 결과를 불러오지 못했습니다</h2><p>연구 백엔드 연결을 확인한 뒤 다시 시도하세요.</p></section></main>; }
  const result = run.result;
  const approximate = run.request.research_grade === "approximate";
  const nullResultMessage = marketResearchNullResultMessage(run);
  return <main>
    <div className="result-local-actions"><Link className="secondary-button" href="/research/market">시장 연구 목록</Link><span className="badge">실전 주문과 분리된 연구</span></div>
    <section className="intro research-intro"><div><p className="eyebrow">{stageLabel(run.stage)} · RUN {run.id.slice(0, 8)}</p><h1>{run.request.market === "KR" ? "한국" : "미국"} {approximate ? "거래량 상위 근사 표본 연구" : "거래량 상위 PIT 연구"}</h1><p className="muted">{run.request.start_date}–{run.request.end_date} · 저장 시각 {run.created_at}{approximate ? " · 과거 날짜별 최대 100개 표본 · PIT 검증 아님" : ""}</p><p className="basis">{marketResearchRunLabel(run)}</p></div></section>
    {!result ? <section className="panel"><h2>{nullResultMessage.heading}</h2><p>{nullResultMessage.detail}</p></section> : <>
      {result.status === "insufficient" && <section className="notice" role="alert"><h2>검증 불충분</h2><p>{result.limitations.join(" ")}</p></section>}
      {result.status === "approximate" && <section className="notice" role="status"><h2>무료 근사 자료 결과</h2><p>{result.limitations.join(" ")}</p></section>}
      {result.status === "ready" && <section className="overview"><article className="hero-card"><span>최종 원화 평가액</span><strong>{metric(run, "final_nav_krw")}원</strong><small>{marketResearchSourceLabel(result.readiness.simulated)} · 시뮬레이션 연구 · PAPER 별도</small></article><article className="metric-card"><span>수익률</span><strong>{metric(run, "return_pct")}%</strong><small>비용·슬리피지 반영</small></article><article className="metric-card"><span>거래 수</span><strong>{metric(run, "trade_count")}건</strong><small>다음 거래일 시가 체결</small></article></section>}
      {result.status === "approximate" && <section className="overview"><article className="hero-card"><span>근사 원화 평가액</span><strong>{metric(run, "final_nav_krw")}원</strong><small>무료 표본 계산 · strict PIT 아님</small></article><article className="metric-card"><span>자료 거래일</span><strong>{metric(run, "coverage_sessions")}일</strong><small>확인된 표본 범위</small></article><article className="metric-card"><span>사용 가능 일봉</span><strong>{metric(run, "usable_candidate_bars")} / {metric(run, "expected_candidate_bars")}</strong><small>표본 내 후보 일봉</small></article><article className="metric-card"><span>제외된 후보 일봉</span><strong>{metric(run, "excluded_nonheld_bars")}건</strong><small>누락·시각 불충분</small></article><article className="metric-card"><span>누락 보유 일봉</span><strong>{metric(run, "missing_held_bars")}건</strong><small>마지막 가격 표시 여부</small></article></section>}
      {result && <section className="panel research-section"><div className="section-title simple"><h2>후보와 근거</h2><span className="muted">당시 membership과 일봉으로 산출</span></div><div className="table-wrap"><table><thead><tr><th>거래일</th><th>순위</th><th>종목</th><th>거래량</th><th>자료 시각</th></tr></thead><tbody>{result.candidate_evidence.slice(-100).map((item) => <tr key={`${item.session}-${item.symbol}`}><td>{item.session}</td><td>{item.rank}</td><td>{item.symbol}</td><td>{marketAmount(item.volume)}</td><td>{item.bar_available_at ?? "확인 불가"}</td></tr>)}</tbody></table></div></section>}
      {result && result.trades.length > 0 && <section className="panel research-section"><div className="section-title simple"><h2>체결 기록</h2><span className="muted">신호일 → 다음 거래일 시가</span></div><div className="table-wrap"><table><thead><tr><th>신호일</th><th>체결일</th><th>종목</th><th>구분</th><th>수량</th><th>근거</th></tr></thead><tbody>{result.trades.map((trade, index) => <tr key={`${trade.fill_session}-${trade.symbol}-${index}`}><td>{trade.signal_session}</td><td>{trade.fill_session}</td><td>{trade.symbol}</td><td>{trade.side === "buy" ? "매수" : "매도"}</td><td>{trade.quantity}</td><td>{trade.rationale}</td></tr>)}</tbody></table></div></section>}
      {result && <section className="panel limitations"><h2>자료와 한계</h2><ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul><p className="basis">입력 SHA-256 {result.input_hash ?? "없음"} · 정책 SHA-256 {result.policy_hash ?? "없음"}</p></section>}
    </>}
  </main>;
}
