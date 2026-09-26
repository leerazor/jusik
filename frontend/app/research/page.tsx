import { researchReportHref } from "@/lib/research-reports";
import Link from "next/link";
import { ComparisonReviewSteps, ComparisonSettings } from "./comparison-settings";
import { OperationsRefresh } from "./lab/operations-refresh";
import { getResearchProgress, type Comparison, type ResearchProgress, type Study } from "@/lib/research-progress";
import { ComparisonResults, ComparisonTakeaway } from "./comparison-results";
import { getStudyNarrative, mandateSummary } from "@/lib/research-narrative";
import { fractionToPercent } from "@/lib/research-decimal";
import styles from "./research.module.css";

export const dynamic = "force-dynamic";
type PageProps = { searchParams: Promise<{ error?: string }> };

function dateTime(value: string | null): string {
  if (!value) return "확인할 수 없음";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "확인할 수 없음" : `${date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}
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
  return <>
    <section className={styles.comparison} id="trial" aria-labelledby="comparison-title">
      <p className={styles.kicker}>01 · 무엇을 바꿔서 시험했나요?</p>
      <h2 id="comparison-title">{narrative?.reading.question ?? "이 자료의 두 연구 설정을 비교합니다"}</h2>
      <ComparisonTakeaway study={study} comparison={comparison} />
      <ComparisonSettings study={study} comparisonId={comparison.id} />
      <ComparisonResults study={study} comparison={comparison} />
      <ComparisonReviewSteps study={study} comparisonId={comparison.id} />
      <Link className={styles.source} href={researchReportHref({ kind: "history", id: study.report_artifact_sha256 })}>이 시험의 근거를 보고서에서 읽기 ↗</Link>
    </section>
    <section className={styles.nextQuestion} aria-labelledby="next-title">
      <p className={styles.kicker}>02 · 여기서 무엇을 판단하면 되나요?</p>
      <h2 id="next-title">다른 기간에도 같은 결과일까요?</h2>
      <p>{narrative?.reading.nextCheck ?? "이 자료에 맞는 설명이 아직 확인되지 않았습니다. 원문과 자료 연결을 확인하기 전에는 투자 판단에 사용하지 마세요."}</p>
      <div className={styles.limit}><strong>아직 알 수 없는 것</strong><span>{narrative ? "앞으로도 같은 결과일지는 모릅니다. 배당·세금이 빠져 있고, 과거의 판단에 그때 알 수 없던 정보가 섞이지 않았는지도 검증 전입니다. 이 결과만으로 실투자 방식을 선택할 단계는 아닙니다." : "설명에 필요한 자료가 일치하지 않아 연구별 결론과 한계를 확정하지 않습니다."}</span></div>
      <p>좋아진 점과 감수한 점을 하나씩 확인했다면, 다른 기간의 결과도 비교해 보세요.</p>
      <Link className={styles.primaryLink} href={`/research/progress#study-${study.id}`}>다른 기간에도 같은 차이인지 확인하기 ↗</Link>
      {narrative && <details className={styles.rulesDetails}><summary>이 연구의 나머지 한계 읽기</summary><ul>{narrative.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul></details>}
    </section>
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
    <section className={styles.hero}>
      <p className={styles.kicker}>처음 읽는 투자 연구</p>
      <h1>더 벌었을까요?<br />위험도 함께 봅니다.</h1>
      <p>연구자가 같은 과거 주가에 두 규칙을 적용한 <strong>가상 시험</strong>입니다. 수익뿐 아니라 하락과 비용을 함께 비교합니다.</p>
    </section>
    {query.error && <div className={styles.alert} role="alert"><h2>연구 도구 요청 결과</h2><p>{query.error === "event-json" ? "시장 이벤트 JSON 배열 형식을 확인하세요." : "연구 도구 요청을 처리하지 못했습니다."} <Link href="/research/lab">연구 도구로 이동</Link></p></div>}
    {availabilityNotice(progress)}
    {featured && <RepresentativeResult study={featured.study} comparison={featured.comparison} />}
    <div className={styles.destinations} aria-label="필요할 때 더 읽기"><Link href="/research/progress"><span>과거 자료로 확인한 차이</span><strong>연구 결과 보기 <span aria-hidden="true">↗</span></strong><p>다른 기간·조건에서도 좋아진 점과 감수한 점이 같았는지 읽습니다.</p></Link><Link href="/research/forward"><span>실제 돈 없이 새 시세로 살펴보기</span><strong>모의 관찰 보기 <span aria-hidden="true">↗</span></strong><p>새 가격을 받은 프로그램이 어떤 판단을 기록했는지 봅니다. 위 연구의 방식과는 별도입니다.</p></Link></div>
    <ResearchConditions />
    <footer className={styles.footer}>자료 공개 {dateTime(progress?.research.published_at ?? null)}<br />화면 확인 {dateTime(progress?.observed_at ?? null)} · 과거 결과는 미래 수익을 보장하지 않습니다.</footer>
  </main>;
}
