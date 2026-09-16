import Link from "next/link";
import {
  getMarketResearchRun,
  marketAmount,
  marketResearchGradeLabel,
  marketResearchCapabilityStatusLabel,
  marketResearchCompletenessLabel,
  marketResearchCounter,
  marketResearchCoverageLabel,
  marketResearchGradeIsConsistent,
  marketResearchEquityCurves,
  marketResearchKrwReturn,
  marketResearchMetric,
  marketResearchNullResultMessage,
  marketResearchProvisionalLabel,
  marketResearchResultStatusLabel,
  marketResearchRunLabel,
  marketResearchSourceLabel,
  type MarketResearchRun,
  type MarketResearchResult,
  type MarketResearchCurve,
} from "@/lib/marketResearch";

export const dynamic = "force-dynamic";

function metric(run: MarketResearchRun, key: string, suffix = ""): string {
  return marketResearchMetric(run.result?.metrics[key], suffix);
}

function counter(run: MarketResearchRun, key: string, suffix = ""): string {
  return marketResearchCounter(run.result?.metrics[key], suffix);
}

function stageLabel(stage: MarketResearchRun["stage"]): string {
  return { pilot: "1년 파일럿", final: "3년 최종", legacy: "기존 실행" }[stage];
}

function CurveChart({ curve, label, suffix }: { curve: MarketResearchCurve; label: string; suffix: string }) {
  if (curve.status === "unavailable") {
    return <p className="empty-inline">{curve.reason ?? "곡선을 확인할 수 없습니다."}</p>;
  }
  const values = curve.points.flatMap((point) => point.value === null ? [] : [point.value]);
  const formatValue = (value: number): string => suffix === "KRW"
    ? `${marketAmount(String(value))}원`
    : marketResearchMetric(String(value), "%");
  const range = `${formatValue(Math.min(...values))}–${formatValue(Math.max(...values))}`;
  return <div className="portfolio-chart">
    <svg viewBox="0 0 100 44" role="img" aria-label={label}>
      {curve.segments.map((points, index) => <polyline key={`${label}-segment-${index}`} points={points} stroke="currentColor" />)}
      {curve.markers.map((point, index) => <circle key={`${label}-point-${index}`} cx={point.x} cy={point.y} r="1.1" fill="currentColor" />)}
    </svg>
    <p>유효한 점 {curve.validPoints}개{curve.invalidPoints > 0 ? ` · 확인 불가 구간 ${curve.invalidPoints}개` : ""} · 단위 {suffix}</p>
    <p>표시 기간 {curve.points[0]?.session}–{curve.points.at(-1)?.session} · 값 범위 {range}</p>
    {curve.reason && <p>{curve.reason}</p>}
  </div>;
}

function EquityDisplay({ result }: { result: MarketResearchResult }) {
  const curves = marketResearchEquityCurves(result);
  return <section className="panel research-section" aria-labelledby="equity-title">
    <div className="section-title simple"><h2 id="equity-title">원화 NAV와 기록된 낙폭</h2><span className="muted">저장된 평가 시계열만 표시</span></div>
    <div className="portfolio-metrics">
      <div><span>계약 근거 원화 수익률</span><strong>{marketResearchKrwReturn(result)}</strong></div>
      <div><span>미국 달러 수익률</span><strong>확인 불가</strong></div>
      <div><span>Benchmark</span><strong>비교 불가</strong></div>
    </div>
    <div className="strategy-grid">
      <article className="strategy-card"><h3>KRW NAV</h3><CurveChart curve={curves.nav} label="저장된 원화 순자산가치 흐름" suffix="KRW" /></article>
      <article className="strategy-card"><h3>기록된 낙폭</h3><CurveChart curve={curves.drawdown} label="저장된 낙폭 흐름" suffix="%" /></article>
    </div>
    <p className="basis">낙폭은 저장된 기록을 그대로 표시하며 회계 재검산이나 DD latch 검증을 수행하지 않습니다. 수익률은 account의 초기 원화 자본과 각 저장 NAV에 근거할 때만 표시합니다. USD 초기 자본과 benchmark 계약·자료는 없어 비교하지 않습니다.</p>
  </section>;
}

export default async function MarketResearchDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let run: MarketResearchRun;
  try {
    run = await getMarketResearchRun(id);
  } catch {
    return <main><section className="notice" role="alert"><h2>시장 연구 결과를 불러오지 못했습니다</h2><p>연구 백엔드 연결을 확인한 뒤 다시 시도하세요.</p></section></main>;
  }
  const result = run.result;
  if (result !== null && !marketResearchGradeIsConsistent(run)) {
    return <main><section className="panel"><h2>결과 확인 불가</h2><p>연구 등급 정보가 일치하지 않아 결과를 표시할 수 없습니다.</p></section></main>;
  }
  const approximate = run.request.research_grade === "approximate";
  const nullResultMessage = marketResearchNullResultMessage(run);
  return <main>
    <div className="result-local-actions"><Link className="secondary-button" href="/research/market">시장 연구 목록</Link><span className="badge">실전 주문과 분리된 연구</span></div>
    <section className="intro research-intro"><div><p className="eyebrow">{stageLabel(run.stage)} · RUN {run.id.slice(0, 8)}</p><h1>{run.request.market === "KR" ? "한국" : "미국"} {approximate ? "거래량 상위 근사 표본 연구" : "거래량 상위 PIT 연구"}</h1><p className="muted">{run.request.start_date}–{run.request.end_date} · 저장 시각 {run.created_at}{approximate ? " · 과거 날짜별 최대 100개 표본 · PIT 검증 아님" : ""}</p><p className="basis">{marketResearchRunLabel(run)}</p></div></section>
    {!result ? <section className="panel"><h2>{nullResultMessage.heading}</h2><p>{nullResultMessage.detail}</p></section> : <>
      <EquityDisplay result={result} />
      {result.status === "insufficient" && <section className="notice" role="alert"><h2>검증 불충분</h2><p>{result.limitations.length > 0 ? result.limitations.join(" ") : "검증에 필요한 자료가 충분하지 않습니다."}</p></section>}
      {result.status === "approximate" && <section className="notice" role="status"><h2>무료 근사 자료 결과</h2><p>{result.limitations.length > 0 ? result.limitations.join(" ") : "근사 자료를 사용한 결과입니다."}</p></section>}

      <section className="panel research-section" aria-labelledby="result-state-title">
        <div className="section-title simple"><h2 id="result-state-title">결과 상태</h2><span className="muted">계약 필드의 잠정 설명</span></div>
        <p className="basis">{marketResearchProvisionalLabel(result)}. 이 표시는 자료 확정성이나 최종 승격 가능성을 판단하지 않습니다.</p>
        <dl className="metric-list">
          <div><dt>결과 상태</dt><dd>{marketResearchResultStatusLabel(result.status)}</dd></div>
          <div><dt>계산 완전성</dt><dd>{marketResearchCompletenessLabel(result.completeness)}</dd></div>
          <div><dt>자료 등급</dt><dd>{marketResearchGradeLabel(result.research_grade)}</dd></div>
          <div><dt>자료 성격</dt><dd>{marketResearchSourceLabel(result.readiness.simulated)}</dd></div>
          <div><dt>준비 상태</dt><dd>{result.readiness.ready ? "준비됨" : "자료 확인 불충분"}</dd></div>
        </dl>
      </section>

      {result.status === "ready" && <section className="overview"><article className="hero-card"><span>최종 원화 평가액</span><strong>{metric(run, "final_nav_krw")}원</strong><small>{marketResearchSourceLabel(result.readiness.simulated)} · 시뮬레이션 연구 · PAPER 별도</small></article><article className="metric-card"><span>계약 근거 원화 수익률</span><strong>{marketResearchKrwReturn(result)}</strong><small>저장 NAV·통화 근거 기반</small></article><article className="metric-card"><span>거래 수</span><strong>{counter(run, "trade_count", "건")}</strong><small>다음 거래일 시가 체결</small></article></section>}
      {result.status === "approximate" && <section className="overview"><article className="hero-card"><span>근사 원화 평가액</span><strong>{metric(run, "final_nav_krw")}원</strong><small>무료 표본 계산 · strict PIT 아님</small></article><article className="metric-card"><span>자료 거래일</span><strong>{counter(run, "coverage_sessions", "일")}</strong><small>확인된 표본 범위</small></article><article className="metric-card"><span>사용 가능 일봉</span><strong>{counter(run, "usable_candidate_bars")} / {counter(run, "expected_candidate_bars")}</strong><small>표본 내 후보 일봉</small></article><article className="metric-card"><span>제외된 후보 일봉</span><strong>{counter(run, "excluded_nonheld_bars", "건")}</strong><small>누락·시각 불충분</small></article><article className="metric-card"><span>누락 보유 일봉</span><strong>{counter(run, "missing_held_bars", "건")}</strong><small>마지막 가격·경과일은 한계에서 확인</small></article></section>}

      <section className="panel research-section" aria-labelledby="coverage-title">
        <div className="section-title simple"><h2 id="coverage-title">자료 coverage</h2><span className="muted">결과 상태와 별도로 확인</span></div>
        <dl className="metric-list">
          <div><dt>자료 거래일</dt><dd>{counter(run, "coverage_sessions", "일")}</dd></div>
          <div><dt>기대 후보 일봉</dt><dd>{counter(run, "expected_candidate_bars", "건")}</dd></div>
          <div><dt>사용 가능 후보 일봉</dt><dd>{counter(run, "usable_candidate_bars", "건")}</dd></div>
          <div><dt>제외된 비보유 일봉</dt><dd>{counter(run, "excluded_nonheld_bars", "건")}</dd></div>
          <div><dt>누락 보유 일봉</dt><dd>{counter(run, "missing_held_bars", "건")}</dd></div>
        </dl>
        <p className="basis">사용 가능 후보 비율: {marketResearchCoverageLabel(result.metrics.usable_candidate_bars, result.metrics.expected_candidate_bars)}</p>
        <p className="basis">누락 보유 일봉 수는 영향받은 세션·종목 수나 마지막 가격의 표시 시점을 뜻하지 않습니다. 마지막 가격과 경과일은 결과의 개별 한계 문구에서만 확인합니다.</p>
      </section>

      <section className="panel research-section" aria-labelledby="readiness-title">
        <div className="section-title simple"><h2 id="readiness-title">자료 준비 상태</h2><span className="muted">확인 시각 {result.readiness.checked_at}</span></div>
        {result.readiness.capabilities.length === 0 ? <p className="empty-inline">확인된 capability 항목이 없습니다. 세부 상태는 확인 불가입니다.</p> : <div className="table-wrap"><table><thead><tr><th>Capability</th><th>상태</th><th>상세</th><th>누락 범위 항목 수</th><th>누락 범위</th></tr></thead><tbody>{result.readiness.capabilities.map((capability) => <tr key={capability.name}><th scope="row">{capability.name}</th><td>{marketResearchCapabilityStatusLabel(capability.status)}</td><td>{capability.detail}</td><td>{capability.missing_ranges.length}개</td><td>{capability.missing_ranges.length > 0 ? capability.missing_ranges.join(" · ") : "없음"}</td></tr>)}</tbody></table></div>}
        <p className="basis">누락 범위 항목 수는 missing_ranges 배열의 항목 수이며, 영향받은 세션·종목 수가 아닙니다.</p>
      </section>

      <section className="panel research-section"><div className="section-title simple"><h2>후보와 근거</h2><span className="muted">당시 membership과 일봉으로 산출</span></div><div className="table-wrap"><table><thead><tr><th>거래일</th><th>순위</th><th>종목</th><th>거래량</th><th>자료 시각</th></tr></thead><tbody>{result.candidate_evidence.slice(-100).map((item) => <tr key={`${item.session}-${item.symbol}`}><td>{item.session}</td><td>{item.rank}</td><td>{item.symbol}</td><td>{marketAmount(item.volume)}</td><td>{item.bar_available_at ?? "확인 불가"}</td></tr>)}</tbody></table></div></section>
      {result.trades.length > 0 && <section className="panel research-section"><div className="section-title simple"><h2>체결 기록</h2><span className="muted">신호일 → 다음 거래일 시가</span></div><div className="table-wrap"><table><thead><tr><th>신호일</th><th>체결일</th><th>종목</th><th>구분</th><th>수량</th><th>근거</th></tr></thead><tbody>{result.trades.map((trade, index) => <tr key={`${trade.fill_session}-${trade.symbol}-${index}`}><td>{trade.signal_session}</td><td>{trade.fill_session}</td><td>{trade.symbol}</td><td>{trade.side === "buy" ? "매수" : "매도"}</td><td>{trade.quantity}</td><td>{trade.rationale}</td></tr>)}</tbody></table></div></section>}
      <section className="panel limitations"><h2>자료와 한계</h2><ul>{result.limitations.length > 0 ? result.limitations.map((item) => <li key={item}>{item}</li>) : <li>기록된 한계가 없습니다. 추가 자료 완전성은 확인 불가입니다.</li>}</ul><p className="basis hashes">입력 SHA-256 {result.input_hash ?? "없음"} · 정책 SHA-256 {result.policy_hash ?? "없음"}</p></section>
    </>}
  </main>;
}
