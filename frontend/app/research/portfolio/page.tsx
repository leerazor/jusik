import Link from "next/link";
import {
  getLatestPortfolioRun,
  getPortfolioStatus,
  researchAmount,
  type PortfolioRun,
  type PortfolioStatus,
} from "@/lib/research";

export const dynamic = "force-dynamic";

const methodLabels = {
  equal: "균등 배분",
  inverse_volatility: "역변동성 배분",
  momentum_top4: "모멘텀 상위 4개·상관 패널티",
} as const;
const gateLabels = {
  none: "외부 변수 필터 없음",
  rates: "금리 필터",
  fx_vix: "환율·VIX 필터",
  stress: "원유·금·회사채 필터",
} as const;
const policyLabels = {
  corrected_control: "체결 수정 대조군",
  reentry_only: "재진입만",
  volatility_only: "변동성 배율만",
  combined: "재진입 + 변동성",
  low_turnover_combined: "저회전 결합",
} as const;
const policyCurveClasses = ["curve-one", "curve-two", "curve-three", "curve-four", "curve-five"] as const;
const lifecycleLabels = {
  risk_exit: "위험 청산 결정",
  liquidation_complete: "청산 완료",
  reentry_ready: "재진입 확인 완료",
  reentry: "재진입 결정",
} as const;

function percent(value: string, digits = 2): string {
  return `${researchAmount(value, digits)}%`;
}

function EquityChart({ run }: { run: PortfolioRun }) {
  const selected = run.heldout.equity.map((point) => Number(point.equity_krw));
  const equal = run.equal_baseline.equity.map((point) => Number(point.equity_krw));
  const all = [...selected, ...equal, Number(run.cash_baseline.final_equity_krw)];
  if (selected.length < 2 || all.some((value) => !Number.isFinite(value))) return null;
  const minimum = Math.min(...all);
  const range = Math.max(...all) - minimum || 1;
  const points = (values: number[]) => values.map((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * 100;
    const y = 40 - ((value - minimum) / range) * 36;
    return `${x},${y}`;
  }).join(" ");
  const cashY = 40 - ((Number(run.cash_baseline.final_equity_krw) - minimum) / range) * 36;
  return (
    <div className="portfolio-chart">
      <svg viewBox="0 0 100 44" role="img" aria-label="선택 정책, 균등 기준, 현금 기준 평가액 비교">
        <line x1="0" x2="100" y1={cashY} y2={cashY} className="cash-line" />
        <polyline points={points(equal)} className="equal-line" />
        <polyline points={points(selected)} className="selected-line" />
      </svg>
      <p><span className="legend selected" />선택 정책 <span className="legend equal" />균등 기준 <span className="legend cash" />현금 기준</p>
    </div>
  );
}

function PolicyEquityChart({ experiment }: { experiment: NonNullable<PortfolioRun["policy_experiment"]> }) {
  const curves = experiment.comparisons.map((comparison) => ({
    policy: comparison.policy,
    values: comparison.base.equity.map((point) => Number(point.equity_krw)),
  }));
  const all = curves.flatMap((curve) => curve.values);
  if (all.length < 2 || all.some((value) => !Number.isFinite(value))) return null;
  const minimum = Math.min(...all);
  const range = Math.max(...all) - minimum || 1;
  const points = (values: number[]) => values.map((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * 100;
    const y = 40 - ((value - minimum) / range) * 36;
    return `${x},${y}`;
  }).join(" ");
  return (
    <div className="portfolio-chart policy-chart">
      <svg viewBox="0 0 100 44" role="img" aria-label="사전 고정한 다섯 정책의 누적 원화 평가액 비교">
        {curves.map((curve, index) => (
          <polyline
            className={policyCurveClasses[index] ?? "curve-five"}
            key={curve.policy}
            points={points(curve.values)}
          />
        ))}
      </svg>
      <p className="policy-legend">
        {curves.map((curve, index) => (
          <span key={curve.policy}><i className={`legend ${policyCurveClasses[index] ?? "curve-five"}`} />{policyLabels[curve.policy]}</span>
        ))}
      </p>
    </div>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function PortfolioContent({ run, status }: { run: PortfolioRun; status: PortfolioStatus | null }) {
  const latestTargets = new Map<string, string>();
  for (const target of run.heldout.weekly_targets) latestTargets.set(target.symbol, target.target_weight);
  const actualPositions = new Map(run.heldout.positions.map((position) => [position.symbol, position]));
  const actualWeights = new Map(run.heldout.positions.map((position) => [position.symbol, position.weight]));
  const symbols = [...new Set([...latestTargets.keys(), ...actualWeights.keys()])].sort();
  const download = (name: string) => `/research/portfolio/download/${run.run_id}/${name}`;
  const latchAt = run.heldout.drawdown_latched_at;
  const currentSources = status?.external_status ?? run.external_status;
  const staleSources = currentSources.filter((source) => source.status !== "success");
  const selectedUnderperformed = Number(run.heldout.metrics.total_return_pct)
    < Number(run.equal_baseline.metrics.total_return_pct);
  const experiment = run.policy_experiment;
  return (
    <>
      {run.heldout.drawdown_latched && (
        <section className="notice quality-warning" role="status">
          <h2>10% 손실 제한 작동 · 현재 목표와 보유는 현금</h2>
          <p>종가 기준 고점 대비 손실 제한이 {latchAt ? new Date(latchAt).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) + " KST에 " : ""}작동해 이후 재진입하지 않았습니다. 아래 수익률에는 이 현금 대기 기간이 포함됩니다.</p>
        </section>
      )}
      {status?.latest_stale && (
        <section className="notice" role="alert"><h2>최근 갱신 실패 · 마지막 성공 결과 표시 중</h2><p>최근 시도 {status.last_attempt_at ?? "기록 없음"} · 오류 코드 {status.error_code ?? "unknown"}. 마지막 성공 결과는 덮어쓰지 않았습니다.</p></section>
      )}
      {status?.status === "running" && (
        <section className="notice" role="status"><h2>새 포트폴리오 연구 실행 중</h2><p>현재 화면은 마지막으로 완전히 저장된 결과입니다.</p></section>
      )}
      {selectedUnderperformed && (
        <section className="notice" role="status">
          <h2>선택 정책이 보유평가에서 동일 비중 추세 기준보다 낮았습니다</h2>
          <p>검증 구간에서 고른 정책 {percent(run.heldout.metrics.total_return_pct)} · 동일 비중 추세 기준 {percent(run.equal_baseline.metrics.total_return_pct)}입니다. 보유평가를 보고 후보를 다시 고르지 않았습니다.</p>
        </section>
      )}
      {staleSources.length > 0 && (
        <section className="notice" role="status"><h2>일부 외부 자료 수집 상태가 최신 성공이 아닙니다</h2><p>{staleSources.map((source) => `${source.source} ${source.status} (최근 성공 ${source.last_success_at ?? "없음"})`).join(" · ")}. 저장된 과거 관측으로 연구했으며 실시간 상태로 해석할 수 없습니다.</p></section>
      )}
      {!run.heldout.complete && <section className="notice" role="alert"><h2>결과 입력 불완전</h2><p>{run.heldout.incomplete_reasons.join(" · ")}</p></section>}
      <section className="portfolio-metrics">
        <article className="hero-card"><span>연속 보유평가 순수익률</span><strong>{percent(run.heldout.metrics.total_return_pct)}</strong><small>{run.heldout_start}–{run.heldout_end} · 1억원 단일 원화 계좌</small></article>
        <MetricCard label="최종 평가액" value={`${researchAmount(run.heldout.metrics.final_equity_krw, 0)}원`} note={`현금 기준 ${researchAmount(run.cash_baseline.final_equity_krw, 0)}원`} />
        <MetricCard label="최대 낙폭" value={percent(run.heldout.metrics.max_drawdown_pct)} note={run.heldout.drawdown_latched ? "10% 제한 작동" : "10% 제한 미작동"} />
        <MetricCard label="비용 2배 수익률" value={percent(run.cost_stress.metrics.total_return_pct)} note="같은 선택 정책 · 재선택 없음" />
      </section>

      <section className="panel research-section">
        <div className="section-title simple"><h2>포트폴리오 평가액 비교</h2><span className="muted">누적 원화 평가액</span></div>
        <EquityChart run={run} />
        <dl className="metric-list">
          <div><dt>선택 정책</dt><dd>{percent(run.heldout.metrics.total_return_pct)}</dd></div>
          <div><dt>동일 비중 추세 전략</dt><dd>{percent(run.equal_baseline.metrics.total_return_pct)}</dd></div>
          <div><dt>거래 수</dt><dd>{run.heldout.metrics.trade_count}건</dd></div>
          <div><dt>회전율</dt><dd>{percent(run.heldout.metrics.turnover_pct)}</dd></div>
          <div><dt>거래 비용</dt><dd>{researchAmount(run.heldout.metrics.transaction_cost_krw, 0)}원</dd></div>
          <div><dt>환전 비용</dt><dd>{researchAmount(run.heldout.metrics.fx_cost_krw, 0)}원</dd></div>
        </dl>
      </section>

      {experiment && (
        <section className="panel research-section">
          <div className="section-title simple"><h2>사전 고정한 5개 정책 비교</h2><span className="muted">후향 비교 · 정책 선택 없음</span></div>
          <p className="basis">
            과거 실행에서 고정한 {methodLabels[experiment.fixed_candidate.method]} · {gateLabels[experiment.fixed_candidate.gate]} 후보를 같은 보유평가 구간과 비용에 적용했습니다. 다섯 행은 동등한 비교 대상이며 성과로 승자를 고르거나 임계값을 조정하지 않았습니다.
          </p>
          {experiment.corrected_selection_changed && (
            <div className="notice" role="status"><p>공통 체결 수정 뒤 12개 검증 후보의 선택은 {experiment.corrected_validation_candidate.id}로 달라졌습니다. 아래 정책 비교는 사전 등록한 {experiment.fixed_candidate.id}를 그대로 유지했습니다.</p></div>
          )}
          <PolicyEquityChart experiment={experiment} />
          <div className="table-wrap"><table><thead><tr><th>정책</th><th>수익률</th><th>최대 낙폭</th><th>비용 2배</th><th>거래</th><th>투자일</th><th>활동 월 거래 평균 / 최대</th><th>청산 / 재진입</th></tr></thead><tbody>
            {experiment.comparisons.map((comparison) => <tr key={comparison.policy}><td>{policyLabels[comparison.policy]}</td><td>{percent(comparison.base.metrics.total_return_pct)}</td><td>{percent(comparison.base.metrics.max_drawdown_pct)}</td><td>{percent(comparison.cost_stress.metrics.total_return_pct)}</td><td>{comparison.base.metrics.trade_count}건</td><td>{percent(comparison.diagnostics.invested_days_pct)}</td><td>{researchAmount(comparison.diagnostics.active_month_trade_average, 1)} / {comparison.diagnostics.active_month_trade_maximum}</td><td>{comparison.diagnostics.exit_count} / {comparison.diagnostics.reentry_count}</td></tr>)}
          </tbody></table></div>
          <p className="basis">투자일은 관측된 UTC 종가일 중 종가 평가액이 현금보다 큰 날의 비율입니다. 월 회전율은 해당 월 각 UTC 일말 평가액 평균으로 거래대금을 나눴으며 달력의 빈 날을 채우지 않았습니다.</p>

          <div className="section-title simple subsection-title"><h3>월별 거래와 정책 상태</h3><span className="muted">0건 월 포함</span></div>
          <div className="table-wrap policy-monthly-table"><table><thead><tr><th>정책</th><th>월</th><th>거래</th><th>월 회전율</th><th>활동</th></tr></thead><tbody>
            {experiment.comparisons.flatMap((comparison) => comparison.diagnostics.monthly.map((month) => <tr key={`${comparison.policy}-${month.month}`}><td>{policyLabels[comparison.policy]}</td><td>{month.month}</td><td>{month.trade_count}건</td><td>{percent(month.turnover_pct)}</td><td>{month.active ? "보유 또는 거래" : "현금 대기"}</td></tr>))}
          </tbody></table></div>

          <div className="policy-events">
            {experiment.comparisons.map((comparison) => <article className="metric-card" key={comparison.policy}><span>{policyLabels[comparison.policy]}</span><strong>{comparison.diagnostics.reentry_count}회 재진입</strong><small>위험 청산 {comparison.diagnostics.exit_count} · 4주 건너뜀 {comparison.diagnostics.frequency_skip_count} · 2%p 구간 {comparison.diagnostics.band_skip_count} · 변동성 축소 {comparison.diagnostics.volatility_scale_event_count}</small></article>)}
          </div>
          <div className="table-wrap"><table><thead><tr><th>정책</th><th>시각 (UTC)</th><th>상태 변화</th><th>설명</th></tr></thead><tbody>
            {experiment.comparisons.flatMap((comparison) => comparison.base.policy_events.filter((event) => event.kind in lifecycleLabels).map((event, index) => <tr key={`${comparison.policy}-${event.at}-${event.kind}-${index}`}><td>{policyLabels[comparison.policy]}</td><td>{event.at}</td><td>{lifecycleLabels[event.kind as keyof typeof lifecycleLabels]}</td><td>{event.detail}</td></tr>))}
          </tbody></table></div>
          <ul className="policy-limitations">{experiment.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          <p className="hash-note">사전 등록 {new Date(experiment.registered_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 명세 SHA-256 {experiment.specification_hash}</p>
        </section>
      )}

      <section className="panel research-section">
        <div className="section-title simple"><h2>검증에서 고른 정책</h2><span className="muted">{run.validation_start}–{run.validation_end}</span></div>
        <h3>{methodLabels[run.selected_candidate.method]} · {gateLabels[run.selected_candidate.gate]}</h3>
        <p className="basis">순수익률 우선, 최대 낙폭·회전율·후보 ID 순으로 동률을 정했습니다. 이후 보유평가 결과로 다시 고르지 않았습니다.</p>
        <div className="table-wrap"><table><thead><tr><th>후보</th><th>검증 수익률</th><th>최대 낙폭</th><th>회전율</th><th>입력</th></tr></thead><tbody>
          {run.validation.map((item) => <tr key={item.candidate.id} className={item.candidate.id === run.selected_candidate.id ? "selected-row" : ""}><td>{methodLabels[item.candidate.method]}<small>{gateLabels[item.candidate.gate]}</small></td><td>{percent(item.metrics.total_return_pct)}</td><td>{percent(item.metrics.max_drawdown_pct)}</td><td>{percent(item.metrics.turnover_pct)}</td><td>{item.complete ? "완전" : "불완전"}</td></tr>)}
        </tbody></table></div>
      </section>

      <section className="panel research-section">
        <div className="section-title simple"><h2>최신 목표와 실제 배분</h2><span className="muted">현금 {researchAmount(run.heldout.equity.at(-1)?.cash_krw ?? run.config.initial_cash_krw, 0)}원</span></div>
        <div className="table-wrap"><table><thead><tr><th>종목</th><th>목표 비중</th><th>실제 비중</th><th>수량</th><th>원화 평가액</th></tr></thead><tbody>
          {symbols.map((symbol) => { const position = actualPositions.get(symbol); return <tr key={symbol}><td>{symbol}</td><td>{percent(latestTargets.get(symbol) ?? "0")}</td><td>{percent(actualWeights.get(symbol) ?? "0")}</td><td>{position?.quantity ?? 0}</td><td>{researchAmount(position?.value_krw ?? "0", 0)}원</td></tr>; })}
        </tbody></table></div>
        <p className="basis">종료 상태를 이어간 다음 재배분 진단입니다. 기준 자산은 최종 평가액이며 주문 지시가 아닙니다. 종목당 20%, 전체 60%, SOXL·TQQQ 합산 20% 상한입니다.</p>
      </section>

      <section className="panel research-section">
        <div className="section-title simple"><h2>종목별 원화 손익 기여</h2><span className="muted">매매 현금흐름 + 종료 보유가치</span></div>
        <div className="table-wrap"><table><thead><tr><th>종목</th><th>기여액</th><th>상관 패널티 입력</th></tr></thead><tbody>
          {Object.entries(run.heldout.contributions_krw).sort(([left], [right]) => left.localeCompare(right)).map(([symbol, contribution]) => <tr key={symbol}><td>{symbol}</td><td>{researchAmount(contribution, 0)}원</td><td>{run.heldout.overlap_diagnostics[symbol] ? percent(run.heldout.overlap_diagnostics[symbol], 3) : "해당 없음"}</td></tr>)}
        </tbody></table></div>
        <p className="basis">기여액에는 해당 종목 매수·매도 현금흐름, 거래·환전 비용, 단주 정산과 종료 보유가치가 포함됩니다. 모멘텀 방식은 과거 60일 양의 상관 평균으로 역변동성 점수를 나눕니다.</p>
      </section>

      <section className="panel research-section">
        <div className="section-title simple"><h2>산출물 내려받기</h2><span className="muted">실행 {run.run_id.slice(0, 10)}</span></div>
        <div className="artifact-links">{run.artifacts.map((name) => <a className="secondary-button" href={download(name)} key={name}>{name}</a>)}</div>
      </section>

      <section className="panel research-section limitations"><div className="section-title simple"><h2>추가 연구와 해석 한계</h2></div>
        <div className="artifact-links">
          <a href="/research/portfolio/download/reports/portfolio-next-research.md">다음 연구 과제</a>
          <a href="/research/portfolio/download/reports/external-research.md">외부 변수 조사</a>
          <a href="/research/portfolio/download/reports/external-comparison.md">외부 변수 비교</a>
          <a href="/research/portfolio/download/reports/model-improvement.md">모델 개선 기록</a>
        </div>
        <ul>{run.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
      <section className="hashes"><p>입력 SHA-256 {run.input_hash}</p><p>코드 SHA-256 {run.code_hash}</p><p>시점 검증 {String(run.point_in_time_verified)} · 미래검증 적격 {String(run.prospective_validation_eligible)} · 자동매매 적격 {String(run.automatic_trading_eligible)}</p></section>
    </>
  );
}

export default async function PortfolioResearchPage() {
  let run: PortfolioRun | null = null;
  let status: PortfolioStatus | null = null;
  let failed = false;
  try {
    [run, status] = await Promise.all([
      getLatestPortfolioRun(),
      getPortfolioStatus(),
    ]);
  } catch {
    failed = true;
  }
  let content;
  if (failed) {
    content = <section className="notice" role="alert"><h2>연구 백엔드에 연결할 수 없습니다</h2><p>8001 포트의 연구 서비스를 확인하세요.</p></section>;
  } else if (run) {
    content = <PortfolioContent run={run} status={status} />;
  } else if (status?.status === "error") {
    content = <section className="notice" role="alert"><h2>첫 포트폴리오 연구가 실패했습니다</h2><p>최근 시도 {status.last_attempt_at ?? "기록 없음"} · 오류 코드 {status.error_code ?? "unknown"}. 입력 수집 상태를 확인한 뒤 백그라운드 연구가 다시 시도합니다.</p></section>;
  } else if (status?.status === "running") {
    content = <section className="panel pending-panel" role="status"><h2>첫 통합 포트폴리오 연구 실행 중</h2><p className="muted">완전히 저장된 뒤 이 페이지에 표시됩니다.</p></section>;
  } else {
    content = <section className="panel pending-panel"><h2>통합 포트폴리오 결과가 아직 없습니다</h2><p className="muted">백그라운드 연구가 처음 완료되면 여기에 표시됩니다.</p></section>;
  }
  return (
    <main>
      <header className="research-result-header"><Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">통합 포트폴리오 연구</span></Link><div className="action-row"><Link className="secondary-button" href="/research/validation">검증 증거</Link><Link className="secondary-button" href="/research/portfolio/dividends">검증된 배당 기여</Link><Link className="secondary-button" href="/research/forward">전진 관찰</Link><Link className="secondary-button" href="/research/history">개발 이력</Link><Link className="secondary-button" href="/research">연구 홈</Link><span className="badge">연구 전용 · 실제 주문 없음</span></div></header>
      <section className="intro research-intro"><div><p className="eyebrow">PORTFOLIO RESEARCH</p><h1>한 계좌로 함께 배분했을 때</h1><p className="muted">16개 종목을 원화 1억원 단일 현금 계좌에서 주간 단위로 재배분한 결과입니다.</p></div></section>
      {content}
    </main>
  );
}
