import Link from "next/link";
import { OperationsRefresh } from "./lab/operations-refresh";
import { compareDecimal, getResearchProgress, type Comparison, type ResearchProgress, type Study } from "@/lib/research-progress";
import {
  getForwardLedger,
  getForwardStatus,
  getProspectiveRegistrationStatus,
  researchAmount,
  type ForwardLedger,
  type ForwardStatus,
  type ProspectiveRegistrationStatus,
} from "@/lib/research";
import { candidateRuleForComparison, getStudyNarrative, mandateSummary, type StudyNarrative } from "@/lib/research-narrative";
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
function formatCapital(value: number): string { return `${(value / 10000).toLocaleString("ko-KR")}만원`; }
function comparisons(studies: Study[]): Comparison[] { return studies.flatMap((study) => study.comparisons); }
function periodScope(study: Study): string {
  if (study.comparisons.length === 0) return "기간 자료 없음";
  const starts = study.comparisons.map((comparison) => comparison.period_start).sort();
  const ends = study.comparisons.map((comparison) => comparison.period_end).sort();
  return `${starts[0]}–${ends[ends.length - 1]}`;
}
function availabilityNotice(progress: ResearchProgress | null): React.ReactNode {
  if (!progress) return <div className={styles.alert} role="alert"><h2>연구 진행 API에 연결할 수 없습니다</h2><p>네트워크 응답 또는 자료 검증이 실패했습니다. 정상 대기나 성과 없음으로 해석하지 않습니다.</p></div>;
  if (progress.research.availability === "invalid") return <div className={styles.alert} role="alert"><h2>연구 자료를 검증할 수 없습니다</h2><p>응답은 받았지만 연구 카탈로그의 형식이나 식별 정보가 유효하지 않습니다.</p></div>;
  if (progress.research.availability === "unavailable") return <div className={styles.alert} role="alert"><h2>연구 자료를 사용할 수 없습니다</h2><p>연구 카탈로그가 제공되지 않았습니다. 자료 없음과 연결 실패를 구분해 표시합니다.</p></div>;
  if (progress.research.studies.length === 0) return <div className={styles.alert} role="status"><h2>공개된 연구가 아직 없습니다</h2><p>카탈로그는 정상 응답했지만 공개된 연구와 비교가 없습니다.</p></div>;
  return null;
}

function percentChange(left: string, right: string, label: string): string {
  const result = compareDecimal(left, right);
  if (result === null || result === 0) return `${label} 변화 판단 자료 부족`;
  return result < 0 ? `${label} 감소` : `${label} 증가`;
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
const registrationStateLabel: Record<string, string> = { not_registered: "미등록", planned: "검증 예정", observing: "검증 중", window_elapsed: "검증 창 종료", identity_mismatch: "식별 정보 불일치", invalid_contract: "계약 검증 실패" };
function GoalSection({ progress }: { progress: ResearchProgress | null }) {
  const featured = featuredComparison(progress);
  const studies = progress?.research.availability === "available" ? progress.research.studies : [];
  const limit = fractionToPercent(mandateSummary.drawdown);
  const leverageLimit = fractionToPercent(mandateSummary.leverage);
  const comparison = featured?.comparison;
  const scope = comparison ? `${featured.study.title} · ${comparison.period_start}–${comparison.period_end} · 비용 ${comparison.cost_multiplier}배 · 현금 ${comparison.cash_statistic === "mean" ? "평균" : "중앙값"} · ${comparison.drawdown_basis === "close_nav" ? "종가 평가액" : "전체 관측 평가액"}` : "지정 대표 비교 없음";
  const riskResult = !comparison || comparison.drawdown_basis === "close_nav" ? "판단 자료 부족" : (() => { const result = compareDecimal(comparison.candidate.max_drawdown_pct, limit); return result !== null && result <= 0 ? "이 과거 비교에서 기준 충족" : "이 과거 비교에서 기준 미충족"; })();
  const leverageResult = !comparison ? "판단 자료 부족" : (() => { const result = compareDecimal(comparison.candidate.max_leverage_pct, leverageLimit); return result !== null && result <= 0 ? "이 과거 비교에서 기준 충족" : "이 과거 비교에서 기준 미충족"; })();
  const cashResult = comparison ? percentChange(comparison.candidate.cash_pct, comparison.baseline.cash_pct, "현금") : "판단 자료 부족";
  const tradeResult = comparison ? `${percentChange(String(comparison.candidate.trade_days), String(comparison.baseline.trade_days), "거래일")} · ${percentChange(comparison.candidate.annual_turnover_pct, comparison.baseline.annual_turnover_pct, "회전율")} · ${percentChange(comparison.candidate.total_cost_krw, comparison.baseline.total_cost_krw, "비용")}` : "판단 자료 부족";
  const rows = [
    { title: "위험 목표", body: `최대 낙폭 ${limit}% 이하를 목표로 합니다.`, evidence: comparison ? `기준 ${percent(comparison.baseline.max_drawdown_pct)} → 후보 ${percent(comparison.candidate.max_drawdown_pct)}` : scope, status: riskResult },
    { title: "레버리지 배분", body: `레버리지 상품 배분 ${leverageLimit}% 범위에서 연구합니다.`, evidence: comparison ? `기준 ${percent(comparison.baseline.max_leverage_pct)} → 후보 ${percent(comparison.candidate.max_leverage_pct)}` : scope, status: leverageResult },
    { title: "현금·투자 비중", body: "불필요한 현금 대기를 줄이고 투자 비중을 높이는 변화를 봅니다.", evidence: comparison ? `기준 ${percent(comparison.baseline.cash_pct)} → 후보 ${percent(comparison.candidate.cash_pct)}` : scope, status: cashResult },
    { title: "거래 부담", body: "거래 빈도·회전율·비용·순수익을 함께 평가합니다.", evidence: comparison ? `거래일 ${comparison.baseline.trade_days} → ${comparison.candidate.trade_days} · 회전율 ${percent(comparison.baseline.annual_turnover_pct)} → ${percent(comparison.candidate.annual_turnover_pct)} · 비용 ${krw(comparison.baseline.total_cost_krw)} → ${krw(comparison.candidate.total_cost_krw)}` : scope, status: tradeResult },
  ];
  const total = comparisons(studies).length;
  return <section className={styles.section} aria-labelledby="goals-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>01 / 기준</span><h2 id="goals-title">목표와 현재 확인 결과</h2><p>{total}개 비교 중 지정 대표 비교 1개에 한정한 요약입니다. 전체 범위는 아래 연구와 성과 비교에서 확인합니다.</p></div></div>{comparison && <div className={styles.goalContext}><strong>{comparison.baseline.label} / {comparison.candidate.label}</strong><span>{scope}</span></div>}<div className={styles.goalList}>{rows.map((row) => <article className={styles.goalRow} key={row.title}><h3>{row.title}</h3><div><p>{row.body}</p><small>{row.evidence}</small></div><strong className={styles.goalStatus}>{row.status}</strong><Link className={styles.goalLink} href={featured ? `/research/progress#study-${featured.study.id}` : "/research/progress#studies-title"}>비교 표 보기 ↗</Link></article>)}</div></section>;
}

function ConditionsSection() {
  const leverageLimit = fractionToPercent(mandateSummary.leverage);
  const drawdownLimit = fractionToPercent(mandateSummary.drawdown);
  const conditions: Array<[string, string]> = [["초기 자본", formatCapital(mandateSummary.capitalKrw)], ["중간 인출", "없음"], ["위험 목표", `초기 자본 포함 최고점 대비 낙폭 ${drawdownLimit}%`], ["레버리지 배분", `${leverageLimit}% 범위`], ["거래 선호", mandateSummary.comparisonPreference], ["과거 자료", `${mandateSummary.lookbackYears}년 확인 기간 요구 · 실제 비교 기간은 연구별로 표시`], ["종목 범위", "기존 종목·현금·광범위 지수 ETF·단기채 ETF 확장"], ["짧은 이력 ETF", "주 연구를 막으면 제외 가능"], ["신호와 주문", "실시간 신호 탐지 · 주문 빈도와 다른 개념"], ["투자기간", mandateSummary.investmentHorizonLabel], ["운영 정책", "실거래 유보 · 기존 PAPER 10% 계약 고정"]];
  return <section className={styles.section} aria-labelledby="conditions-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>02 / 범위</span><h2 id="conditions-title">목표를 적용하는 운용 조건</h2><p>설정값과 자료가 실제로 다룬 범위를 섞지 않습니다.</p></div></div><dl className={styles.conditions}>{conditions.map(([term, description]) => <div className={styles.condition} key={term}><dt>{term}</dt><dd>{description}</dd></div>)}</dl></section>;
}

function studyResult(study: Study): string {
  const comparison = study.comparisons.find((item) => item.id.includes("continuous")) ?? study.comparisons[0];
  if (!comparison) return "비교 수치 없음";
  const candidateRule = candidateRuleForComparison(study, comparison.id);
  return `${comparison.baseline.label} → ${comparison.candidate.label}${candidateRule ? ` (${candidateRule.label})` : ""} · ${comparison.period_start}–${comparison.period_end} · 비용 ${comparison.cost_multiplier}배 · 현금 ${comparison.cash_statistic === "mean" ? "평균" : "중앙값"} · 순수익률 ${percent(comparison.baseline.net_return_pct)} → ${percent(comparison.candidate.net_return_pct)} · 현금 ${percent(comparison.baseline.cash_pct)} → ${percent(comparison.candidate.cash_pct)} · 낙폭 ${percent(comparison.baseline.max_drawdown_pct)} → ${percent(comparison.candidate.max_drawdown_pct)}`;
}
function StudyCard({ study }: { study: Study }) {
  const narrative: StudyNarrative | null = getStudyNarrative(study);
  return <article className={styles.study} id={`study-${study.id}`}><div className={styles.studyHead}><div><span className={styles.sectionNo}>연구 질문</span><h3>{study.title}</h3></div><span className={styles.studyMeta}>공개 {dateTime(study.published_at)}</span></div>{narrative ? <><p className={styles.studyQuestion}>{narrative.question}</p><p className={styles.studyChange}><strong>변경 묶음:</strong> {narrative.baselineRules.join(" · ")} → {narrative.candidateRules.join(" · ")}</p><p className={styles.studyResult}><strong>비교 결과:</strong> {studyResult(study)}</p><p className={styles.studyResult}><strong>해석과 결정:</strong> {narrative.conclusion} 결정 기록 없음.</p><p className={styles.studyLimit}>{narrative.limitations.join(" ")}</p></> : <div className={styles.missing}><strong>연구 설명을 확인할 수 없습니다.</strong> 등록된 식별 정보와 일치하지 않습니다. API가 제공한 제목·수치·보고서 링크는 그대로 표시합니다.</div>}<div className={styles.studyFoot}><span>{study.comparisons.length}개 비교 · {study.universe_symbols.length}종목 · {periodScope(study)} · 배당·세금 제외</span><Link href={`/research/progress#study-${study.id}`}>성과 비교 전체 보기 ↗</Link><Link href={`/research/history/download/${study.report_artifact_sha256}`}>원본 보고서 ↗</Link></div></article>;
}
function StudiesSection({ progress }: { progress: ResearchProgress | null }) {
  const studies = progress?.research.availability === "available" ? [...progress.research.studies].sort((left, right) => right.published_at.localeCompare(left.published_at)) : [];
  const comparisonTotal = studies.reduce((total, study) => total + study.comparisons.length, 0);
  return <section className={styles.section} aria-labelledby="studies-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>03 / 근거</span><h2 id="studies-title">목표를 위해 확인한 연구</h2><p>개요는 질문과 결과를 압축하고, 기존 방식·시험 방식·고정 조건과 {comparisonTotal}개 비교 표는 성과 비교에서 자세히 확인합니다.</p></div><Link className={styles.textLink} href="/research/progress">성과 비교 전체 보기 ↗</Link></div>{studies.length > 0 && <div className={styles.studyList}>{studies.map((study) => <StudyCard key={study.id} study={study} />)}</div>}</section>;
}

async function ObservationSection() {
  const [statusResult, ledgerResult, registrationResult] = await Promise.allSettled([getForwardStatus(), getForwardLedger(), getProspectiveRegistrationStatus()]);
  const status: ForwardStatus | null = statusResult.status === "fulfilled" ? statusResult.value : null;
  const ledger: ForwardLedger | null = ledgerResult.status === "fulfilled" ? ledgerResult.value : null;
  const registration: ProspectiveRegistrationStatus | null = registrationResult.status === "fulfilled" ? registrationResult.value : null;
  const registered = registration?.registration;
  const identityMatches = Boolean(status && registered && registered.session_id === status.session.id && registered.policy_hash === status.session.policy_hash && registered.source_run_id === status.session.source_run_id && registration?.status !== "identity_mismatch" && registration?.status !== "invalid_contract");
  return <section className={styles.section} aria-labelledby="observation-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>04 / 별도 운용</span><h2 id="observation-title">고정 PAPER 관찰</h2><p>비교 후보의 채택 판단과 분리된 관찰 화면입니다.</p></div></div>{!status && !ledger ? <div className={styles.alert} role="alert"><h3>관찰 자료에 연결할 수 없습니다</h3><p>관찰 API 응답을 확인할 수 없습니다.</p></div> : !status || !ledger ? <div className={styles.alert} role="alert"><h3>관찰 자료 일부를 확인할 수 없습니다</h3><p>정책 상태와 원장 중 하나의 응답만 확인되었습니다. 가상 관찰 화면에서 세부 상태를 확인하세요.</p></div> : <div className={styles.forward}><div><h3>PAPER 10% 방어 정책</h3><p>연구 목표 20%와 다른 고정 조건입니다. 새 시세부터 쌓는 기록이며, 연구 후보의 검증 완료나 실거래 준비를 의미하지 않습니다.</p><div className={styles.actionRow}><Link className={styles.primary} href="/research/forward">관찰 상세 보기 ↗</Link></div></div><dl><div><dt>정책 hash</dt><dd title={status.session.policy_hash}>{status.session.policy_hash.slice(0, 12)}…</dd></div><div><dt>활성화 시각</dt><dd>{dateTime(status.session.activated_at)}</dd></div><div><dt>다음 정기 시각</dt><dd>{dateTime(status.session.next_due_at)}</dd></div><div><dt>기록 수</dt><dd>체결 {ledger.fills.length}건 · 시세 {status.feed.items.length}종목</dd></div><div><dt>검증 창</dt><dd>{registrationResult.status !== "fulfilled" ? "확인할 수 없음" : !identityMatches || !registered ? "식별 불일치 또는 미등록" : `${dateTime(registered.evaluation_start_at)} ~ ${dateTime(registered.evaluation_end_at)}`}</dd></div><div><dt>검증 상태</dt><dd>{registration?.status ? registrationStateLabel[registration.status] ?? "확인할 수 없음" : "확인할 수 없음"}</dd></div></dl></div>}</section>;
}

export default async function ResearchHubPage({ searchParams }: PageProps) {
  const query = await searchParams;
  let progress: ResearchProgress | null = null;
  try { progress = await getResearchProgress(); } catch { progress = null; }
  return <main className={styles.main}><OperationsRefresh /><section className={styles.hero}><div><p className={styles.kicker}>INVESTOR RESEARCH</p><h1>연구 개요</h1><p className={styles.lede}>목표 → 변경한 운용 방식 → 검증 결과 → 결정 상태의 순서로 읽습니다. 확인된 과거 비교와 아직 답하지 못한 질문을 분리해 보여줍니다.</p></div><div className={styles.heroMeta}><strong>자료 기준 시각</strong><small>공개 {dateTime(progress?.research.published_at ?? null)}</small><small>화면 확인 {dateTime(progress?.observed_at ?? null)}</small><small>두 시각은 데이터가 만들어진 때와 페이지가 확인한 때를 뜻합니다.</small></div></section>{query.error && <div className={styles.alert} role="alert"><h2>연구 도구 요청 결과</h2><p>{query.error === "event-json" ? "시장 이벤트 JSON 배열 형식을 확인하세요." : "연구 도구 요청을 처리하지 못했습니다."} <Link className={styles.textLink} href="/research/lab">연구 도구로 이동</Link></p></div>}{availabilityNotice(progress)}<GoalSection progress={progress} /><ConditionsSection /><StudiesSection progress={progress} /><ObservationSection /></main>;
}
