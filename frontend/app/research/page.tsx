import Link from "next/link";
import { OperationsRefresh } from "./lab/operations-refresh";
import { compareDecimal, getResearchProgress, type Comparison, type ResearchProgress, type Study } from "@/lib/research-progress";
import { researchAmount } from "@/lib/research";
import { candidateRuleForComparison, getStudyNarrative, mandateSummary } from "@/lib/research-narrative";
import { fractionToPercent } from "@/lib/research-decimal";
import styles from "./research.module.css";

export const dynamic = "force-dynamic";
type PageProps = { searchParams: Promise<{ error?: string }> };

function dateTime(value: string | null): string {
  if (!value) return "확인할 수 없음";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "확인할 수 없음" : `${date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}
function percent(value: string): string { return `${researchAmount(value, 2)}%`; }
function krw(value: string): string { return `${researchAmount(value, 0)}원`; }
function featuredComparison(progress: ResearchProgress | null): { study: Study; comparison: Comparison } | null {
  const id = progress?.research.featured_comparison_id;
  if (!id || progress?.research.availability !== "available") return null;
  for (const study of progress.research.studies) {
    const comparison = study.comparisons.find((item) => item.id === id);
    if (comparison) return { study, comparison };
  }
  return null;
}
function availabilityNotice(progress: ResearchProgress | null): React.ReactNode {
  if (!progress) return <div className={styles.alert} role="alert"><h2>연구 자료에 연결할 수 없습니다</h2><p>응답을 받지 못했거나 검증하지 못했습니다. 연구 결과가 없다는 뜻은 아닙니다.</p></div>;
  if (progress.research.availability === "invalid") return <div className={styles.alert} role="alert"><h2>연구 자료를 검증할 수 없습니다</h2><p>응답은 받았지만 자료의 형식이나 식별 정보가 맞지 않아 결과를 표시하지 않습니다.</p></div>;
  if (progress.research.availability === "unavailable") return <div className={styles.alert} role="alert"><h2>연구 자료를 사용할 수 없습니다</h2><p>연구 목록이 제공되지 않았습니다. 공개된 연구가 없는 상태와는 다릅니다.</p></div>;
  if (progress.research.studies.length === 0) return <div className={styles.alert} role="status"><h2>공개된 연구가 아직 없습니다</h2><p>자료는 정상적으로 확인했지만 공개된 연구와 비교가 없습니다.</p></div>;
  if (!featuredComparison(progress)) return <div className={styles.alert} role="status"><h2>대표 비교가 지정되지 않았습니다</h2><p>임의의 연구를 골라 결론을 만들지 않습니다. 연구 결과에서 공개된 자료를 확인할 수 있습니다.</p></div>;
  return null;
}

function RepresentativeResult({ study, comparison }: { study: Study; comparison: Comparison }) {
  const narrative = getStudyNarrative(study);
  const candidateRule = candidateRuleForComparison(study, comparison.id);
  const higherReturn = compareDecimal(comparison.candidate.net_return_pct, comparison.baseline.net_return_pct) === 1;
  const lowerCash = compareDecimal(comparison.candidate.cash_pct, comparison.baseline.cash_pct) === -1;
  const higherDrawdown = compareDecimal(comparison.candidate.max_drawdown_pct, comparison.baseline.max_drawdown_pct) === 1;
  const higherCost = compareDecimal(comparison.candidate.total_cost_krw, comparison.baseline.total_cost_krw) === 1;
  const conclusion = !narrative ? "이 연구의 결론 설명을 확인할 수 없습니다." : higherReturn && lowerCash && higherDrawdown && higherCost ? "투자하지 않은 돈의 비중은 줄고 수익률은 높아졌지만, 하락 폭과 비용도 커졌습니다." : narrative.conclusion;
  const tradeoffs = [
    higherDrawdown ? "하락 폭이 커졌습니다" : null,
    higherCost ? "거래 비용이 늘었습니다" : null,
    compareDecimal(comparison.candidate.trade_days.toString(), comparison.baseline.trade_days.toString()) === 1 ? "거래한 날이 늘었습니다" : null,
    compareDecimal(comparison.candidate.annual_turnover_pct, comparison.baseline.annual_turnover_pct) === 1 ? "사고판 비율이 늘었습니다" : null,
  ].filter((value): value is string => value !== null);
  const rows = [
    { label: "돈이 얼마나 늘었나", meaning: "기간 누적 수익률 · 연 수익률 아님", baseline: percent(comparison.baseline.net_return_pct), candidate: percent(comparison.candidate.net_return_pct) },
    { label: "중간에 얼마나 떨어졌나", meaning: "최대 낙폭 · 평가액 고점 대비 하락", baseline: percent(comparison.baseline.max_drawdown_pct), candidate: percent(comparison.candidate.max_drawdown_pct) },
    { label: "투자하지 않은 돈의 비중", meaning: `평가액 중 현금 비중 · ${comparison.cash_statistic === "mean" ? "평균" : "중앙값"}`, baseline: percent(comparison.baseline.cash_pct), candidate: percent(comparison.candidate.cash_pct) },
    { label: "거래에 든 비용", meaning: "연구 계산에 반영된 비용 합계", baseline: krw(comparison.baseline.total_cost_krw), candidate: krw(comparison.candidate.total_cost_krw) },
    { label: "거래한 날", meaning: "거래 발생 날짜 수 · 주문 횟수 아님", baseline: `${comparison.baseline.trade_days}일`, candidate: `${comparison.candidate.trade_days}일` },
    { label: "자산을 사고판 비율", meaning: "연환산 회전율 · 높을수록 거래 부담 증가", baseline: percent(comparison.baseline.annual_turnover_pct), candidate: percent(comparison.candidate.annual_turnover_pct) },
  ];
  return <>
    <section className={styles.conclusion} aria-labelledby="conclusion-title">
      <p className={styles.kicker}>공개된 과거 연구의 결론</p>
      <h2 id="conclusion-title">{conclusion}</h2>
      <p>{narrative ? "아래 대표 비교에서 확인한 차이입니다. 실제 투자에 쓸 방식으로 채택됐다는 뜻은 아닙니다." : "등록된 연구와 식별 정보가 일치하지 않습니다. 확인된 수치와 원본 보고서는 아래에서 볼 수 있습니다."}</p>
      <div className={styles.limit}><strong>여기까지 믿을 수 있어요</strong><span>{narrative ? "배당·세금은 빠져 있습니다. 당시 알 수 있었던 정보만 썼는지도 검증 전이므로 미래 결과로 일반화할 수 없습니다." : "수치 자료의 검증과 결론 설명의 식별 확인은 별개입니다. 이 자료에 기존 연구의 해석을 붙이지 않습니다."}</span></div>
    </section>
    <section className={styles.comparison} aria-labelledby="comparison-title">
      <div className={styles.sectionHead}><div><p className={styles.kicker}>결론의 근거 · 지정된 대표 비교 1개</p><h2 id="comparison-title">무엇이 달라졌나요?</h2></div><Link href={`/research/progress#study-${study.id}`}>모든 비교 보기 ↗</Link></div>
      <p className={styles.question}>{narrative?.question.replaceAll("재조정", "보유 비중 조정") ?? study.title}</p>
      <p className={styles.scope}>{comparison.period_start}–{comparison.period_end} · 비용 {comparison.cost_multiplier}배 · 현금 {comparison.cash_statistic === "mean" ? "평균" : "중앙값"} · 낙폭은 {comparison.drawdown_basis === "close_nav" ? "종가 평가액" : "전체 관측 평가액"} 기준</p>
      <div className={styles.compareHead}><span>같은 조건에서 비교</span><div><strong>기존 방식</strong><small>{comparison.baseline.label}</small></div><div><strong>시험한 방식</strong><small>{comparison.candidate.label}{candidateRule ? ` · ${candidateRule.label}` : ""}</small></div></div>
      {narrative && <details className={styles.rulesDetails}><summary>두 방식은 무엇이 다른가요? · 규칙과 용어</summary><div className={styles.ruleRow}><span>바꾼 규칙</span><p>{narrative.baselineRules.join(" · ")}</p><p>{narrative.candidateRules.join(" · ")}</p></div><p>투자 상한은 돈을 넣는 최대 비중입니다. 재조정은 보유 종목에 넣는 돈의 비중을 다시 맞추는 일입니다. 연 변동성 목표는 연간 수익률의 흔들림을 조절하는 목표이며, 약속된 수익률이나 손실 한도가 아닙니다.</p></details>}
      <dl className={styles.metricRows}>{rows.map((row) => <div className={styles.metricRow} key={row.label}><dt>{row.label}<small>{row.meaning}</small></dt><dd><span className="sr-only">기존 방식 </span>{row.baseline}</dd><dd><span className="sr-only">시험한 방식 </span>{row.candidate}</dd></div>)}</dl>
      <p className={styles.tradeoff}><strong>함께 감수한 점</strong> {tradeoffs.length > 0 ? `${tradeoffs.join(". ")}.` : "수익·현금만으로 개선을 판단할 수 없습니다. 하락 폭과 거래 부담을 함께 보세요."} {comparison.drawdown_basis === "close_nav" ? "종가 기준 하락 폭으로는 모든 관측 시점의 위험 목표 충족을 판단할 수 없습니다." : "하락 폭은 이 과거 비교의 범위에서만 확인된 값입니다."}</p>
      <p className={styles.scope}>최고 수익을 골라낸 비교나 최종 채택안이 아닙니다. 전체 변경 규칙과 다른 기간의 결과는 연구 결과에서 확인하세요.</p>
      <Link className={styles.source} href={`/research/history/download/${study.report_artifact_sha256}`}>이 비교의 원본 보고서 ↗</Link>
    </section>
    <section className={styles.nextQuestion} aria-labelledby="next-title"><p className={styles.kicker}>아직 답하지 못한 질문</p><h2 id="next-title">{narrative ? "다른 기간과 배당·세금까지 반영해도 같은 결과일까요?" : "이 자료에 연결된 결론을 확인할 수 있을까요?"}</h2><p>{narrative ? "과거 결과를 투자 판단에 쓰려면 추가 확인이 필요합니다. 아래는 연구에 기록된 한계이며, 후속 작업이 실행 중이라는 뜻은 아닙니다." : "원본 보고서와 식별 정보를 확인해야 합니다. 일치가 확인되기 전에는 연구별 해석을 표시하지 않습니다."}</p>{narrative && <ul>{narrative.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>}</section>
  </>;
}

function ResearchConditions() {
  const conditions: Array<[string, string]> = [
    ["초기 자본", `${(mandateSummary.capitalKrw / 10000).toLocaleString("ko-KR")}만원 · 중간 인출 없음`],
    ["위험 목표", `초기 자본을 포함한 최고 평가액에서 ${fractionToPercent(mandateSummary.drawdown)}% 이내 하락 · 손실 보장 아님`],
    ["레버리지 상품", `배분 ${fractionToPercent(mandateSummary.leverage)}% 범위`],
    ["거래 선호", mandateSummary.comparisonPreference],
    ["과거 확인 기간", `${mandateSummary.lookbackYears}년 요구 · 실제 확보 기간은 비교마다 다름`],
    ["종목 범위", "기존 종목·현금·광범위 지수 ETF·단기채 ETF · 짧은 이력 ETF는 주 연구를 막으면 제외 가능"],
    ["신호와 주문", "실시간 신호 탐지 · 주문 빈도와는 별개"],
    ["투자기간", mandateSummary.investmentHorizonLabel],
    ["운영 조건", "실거래 유보 · 별도 모의 관찰의 PAPER 10% 계약 유지"],
  ];
  return <details className={styles.conditions}><summary>연구 목표와 전체 운용 조건 보기</summary><p>불필요한 현금과 잦은 거래를 줄이면서 위험을 관리하는 방법을 연구합니다. 아래는 목표이며 달성 결과가 아닙니다.</p><dl>{conditions.map(([term, description]) => <div key={term}><dt>{term}</dt><dd>{description}</dd></div>)}</dl></details>;
}

export default async function ResearchHubPage({ searchParams }: PageProps) {
  const query = await searchParams;
  let progress: ResearchProgress | null = null;
  try { progress = await getResearchProgress(); } catch { progress = null; }
  const featured = featuredComparison(progress);
  return <main className={styles.main}>
    <OperationsRefresh />
    <section className={styles.hero}><p className={styles.kicker}>투자 연구 노트</p><h1>한눈에 보기</h1><p>현금으로 기다리는 돈과 잦은 거래를 줄이면,<br className={styles.desktopBreak} /> 위험을 감당하면서 더 나은 결과를 얻을 수 있을까요?</p></section>
    {query.error && <div className={styles.alert} role="alert"><h2>연구 도구 요청 결과</h2><p>{query.error === "event-json" ? "시장 이벤트 JSON 배열 형식을 확인하세요." : "연구 도구 요청을 처리하지 못했습니다."} <Link href="/research/lab">연구 도구로 이동</Link></p></div>}
    {availabilityNotice(progress)}
    {featured && <RepresentativeResult study={featured.study} comparison={featured.comparison} />}
    <div className={styles.destinations}><Link href="/research/progress"><span>과거 자료로 확인한 차이</span><strong>연구 결과 보기 <span aria-hidden="true">↗</span></strong><p>연구별 질문과 결론, 자세한 비교 표를 읽습니다.</p></Link><Link href="/research/forward"><span>새로 들어온 시세로 쌓는 기록</span><strong>모의 관찰 보기 <span aria-hidden="true">↗</span></strong><p>별도 가상 계좌의 기록입니다. 연구 후보가 자동 반영되지는 않습니다.</p></Link></div>
    <ResearchConditions />
    <footer className={styles.footer}>자료 공개 {dateTime(progress?.research.published_at ?? null)}<br />화면 확인 {dateTime(progress?.observed_at ?? null)} · 과거 결과는 미래 수익을 보장하지 않습니다.</footer>
  </main>;
}
