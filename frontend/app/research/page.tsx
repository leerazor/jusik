import Link from "next/link";
import { OperationsRefresh } from "./lab/operations-refresh";
import { compareDecimal, getResearchProgress, type ResearchProgress, type Study } from "@/lib/research-progress";
import { getStudyNarrative, mandateSummary, type StudyNarrative } from "@/lib/research-narrative";
import styles from "./research.module.css";

export const dynamic = "force-dynamic";
type PageProps = { searchParams: Promise<{ error?: string }> };

function dateTime(value: string | null): string {
  if (!value) return "확인할 수 없음";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "확인할 수 없음" : `${date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}
function formatCapital(value: number): string { return `${(value / 10000).toLocaleString("ko-KR")}만원`; }
function list(items: string[]): React.ReactNode { return <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>; }
function targetStatus(studies: Study[], predicate: (study: Study) => boolean): string {
  const relevant = studies.filter((study) => study.comparisons.length > 0);
  if (relevant.length === 0) return "자료 없음";
  return relevant.every(predicate) ? "각 비교의 결과 확인" : "비교 결과에서 상충 확인";
}
function riskStatus(studies: Study[]): string { return targetStatus(studies, (study) => study.comparisons.every((comparison) => compareDecimal(comparison.candidate.max_drawdown_pct, "20") === -1)); }
function availabilityNotice(progress: ResearchProgress | null): React.ReactNode {
  if (!progress) return <div className={styles.alert} role="alert"><h2>연구 진행 API에 연결할 수 없습니다</h2><p>네트워크 응답 또는 자료 검증이 실패했습니다. 정상 대기나 성과 없음으로 해석하지 않습니다.</p></div>;
  if (progress.research.availability === "invalid") return <div className={styles.alert} role="alert"><h2>연구 자료를 검증할 수 없습니다</h2><p>응답은 받았지만 연구 카탈로그의 형식이나 식별 정보가 유효하지 않습니다. API의 원본 자료를 확인하세요.</p></div>;
  if (progress.research.availability === "unavailable") return <div className={styles.alert} role="alert"><h2>연구 자료를 사용할 수 없습니다</h2><p>연구 카탈로그가 제공되지 않았습니다. 자료가 없다는 뜻과 transport 실패를 구분해 표시합니다.</p></div>;
  if (progress.research.studies.length === 0) return <div className={styles.alert} role="status"><h2>공개된 연구가 아직 없습니다</h2><p>카탈로그는 정상 응답했지만 공개된 연구와 비교가 없습니다.</p></div>;
  return null;
}

function GoalSection({ progress }: { progress: ResearchProgress | null }) {
  const studies = progress?.research.availability === "available" ? progress.research.studies : [];
  const turnover = targetStatus(studies, (study) => study.comparisons.some((comparison) => compareDecimal(comparison.candidate.annual_turnover_pct, comparison.baseline.annual_turnover_pct) !== null));
  return <section className={styles.section} aria-labelledby="goals-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>01 / 기준</span><h2 id="goals-title">연구 개요</h2><p>목표와 운용 조건을 먼저 읽고, 아래 연구가 어느 범위까지 답했는지 확인합니다.</p></div></div><div className={styles.goalList}><article className={styles.goalRow}><h3>위험 목표</h3><p>초기 자본을 포함한 총 평가액의 running peak NAV 대비 최대 낙폭을 20% 안에서 관리합니다.</p><small>{mandateSummary.drawdownReference}</small><strong className={styles.goalStatus}>{riskStatus(studies)}</strong></article><article className={styles.goalRow}><h3>현금·투자 비중</h3><p>불필요한 현금 대기를 줄이고 투자 비중을 높이는 변화를 비교합니다.</p><small>정량 임계값을 새로 만들지 않고 기준선과 후보의 현금·수익·낙폭을 함께 봅니다.</small><strong className={styles.goalStatus}>{studies.length ? "비교별 변화 확인" : "자료 없음"}</strong></article><article className={styles.goalRow}><h3>거래 부담</h3><p>잦은 거래를 피하면서 거래 빈도, 회전율, 비용, 비용 차감 순수익을 함께 평가합니다.</p><small>단일 점수나 우선순위는 설정하지 않았습니다.</small><strong className={styles.goalStatus}>{turnover}</strong></article></div></section>;
}

function ConditionsSection() {
  const conditions = [["초기 자본", formatCapital(mandateSummary.capitalKrw)], ["중간 인출", mandateSummary.interimWithdrawals === "none" ? "없음" : mandateSummary.interimWithdrawals], ["레버리지 배분", `${Number(mandateSummary.leverage) * 100}% 범위`], ["과거 lookback", `${mandateSummary.lookbackYears}년 요구 · 실제 비교 기간은 연구별로 표시`], ["종목 범위", mandateSummary.universeExpansion.join(" · ")], ["짧은 이력 ETF", "주 연구를 막으면 제외 가능"], ["신호와 주문", "실시간 신호 탐지 · 실거래 주문 아님"], ["투자기간", "미정"], ["운영 정책", "실거래 유보 · 기존 PAPER 10% 계약 고정"]];
  return <section className={styles.section} aria-labelledby="conditions-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>02 / 범위</span><h2 id="conditions-title">목표를 적용하는 운용 조건</h2><p>설정값과 자료가 실제로 다룬 범위를 섞지 않습니다.</p></div></div><dl className={styles.conditions}>{conditions.map(([term, description]) => <div className={styles.condition} key={term}><dt>{term}</dt><dd>{description}</dd></div>)}</dl></section>;
}

function StudyCard({ study }: { study: Study }) {
  const narrative: StudyNarrative | null = getStudyNarrative(study);
  return <article className={styles.study} id={study.id}><div className={styles.studyHead}><div><span className={styles.sectionNo}>연구 질문</span><h3>{study.title}</h3></div><span className={styles.studyMeta}>공개 {dateTime(study.published_at)}</span></div>{narrative ? <><p className={styles.studyQuestion}>{narrative.question}</p><div className={styles.studyGrid}><div className={styles.studyBlock}><h4>관련 목표 · 해결하려는 문제</h4>{list(narrative.relatedGoals)}</div><div className={styles.studyBlock}><h4>기존 방식</h4>{list(narrative.baselineRules)}</div><div className={styles.studyBlock}><h4>시험 방식</h4>{list(narrative.candidateRules)}</div><div className={styles.studyBlock}><h4>고정 조건</h4>{list(narrative.fixedConditions)}</div><div className={styles.studyBlock}><h4>이 자료의 한계</h4>{list(narrative.limitations)}</div></div><p className={styles.studyResult}><strong>결과와 결정 분리:</strong> {narrative.conclusion} <strong>결정 기록 없음.</strong></p></> : <div className={styles.missing}><strong>연구 설명을 확인할 수 없습니다.</strong> 식별자 또는 source/result/report 해시가 등록된 자료와 일치하지 않습니다. API가 제공한 제목·비교 수치·보고서 링크는 그대로 표시합니다.</div>}<div className={styles.studyFoot}><span>{study.comparisons.length}개 비교 · {study.universe_symbols.length}종목 · 과거 가격만 · 배당·세금 제외</span><Link href={`/research/progress#${study.id}`}>성과 비교에서 전체 수치 보기 ↗</Link><Link href={`/research/history/download/${study.report_artifact_sha256}`}>원본 보고서 ↗</Link>{narrative && <span title={`${study.source_sha256} / ${study.result_sha256}`}>근거 해시 확인됨 · {narrative.sourceReference}</span>}</div></article>;
}

function StudiesSection({ progress }: { progress: ResearchProgress | null }) {
  const studies = progress?.research.availability === "available" ? [...progress.research.studies].sort((left, right) => right.published_at.localeCompare(left.published_at)) : [];
  return <section className={styles.section} aria-labelledby="studies-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>03 / 근거</span><h2 id="studies-title">목표를 위해 확인한 연구</h2><p>각 연구의 질문·변경·고정 조건·결과·결정 상태를 한 항목에서 연결합니다.</p></div><Link className={styles.textLink} href="/research/progress">성과 비교 전체 보기 ↗</Link></div>{studies.length > 0 && <div className={styles.studyList}>{studies.map((study) => <StudyCard key={study.id} study={study} />)}</div>}</section>;
}

function ObservationSection() { return <section className={styles.section} aria-labelledby="observation-title"><div className={styles.sectionHead}><div><span className={styles.sectionNo}>04 / 다음 확인</span><h2 id="observation-title">현재 자료 다음에 확인할 것</h2></div></div><div className={styles.forward}><div><h3>고정 PAPER 10% 가상 관찰</h3><p>새 시세부터 쌓는 별도 관찰 기록입니다. 연구 목표인 20%와 다른 방어 조건이며, 비교 후보의 채택이나 실거래 준비를 뜻하지 않습니다.</p><div className={styles.actionRow}><Link className={styles.primary} href="/research/forward">가상 관찰 보기 ↗</Link><Link className={styles.secondary} href="/research/history">근거 기록 ↗</Link></div></div><dl><div><dt>관찰 목적</dt><dd>고정 PAPER 운용 기록</dd></div><div><dt>실거래</dt><dd>유보</dd></div><div><dt>평가 종료 조건</dt><dd>자료에 없음</dd></div><div><dt>다음 질문</dt><dd>독립 기간 재현 검증</dd></div></dl></div></section>; }

export default async function ResearchHubPage({ searchParams }: PageProps) { const query = await searchParams; let progress: ResearchProgress | null = null; try { progress = await getResearchProgress(); } catch { progress = null; } return <main className={styles.main}><OperationsRefresh /><section className={styles.hero}><div><p className={styles.kicker}>INVESTOR RESEARCH / 2026.09</p><h1>연구 개요</h1><p className={styles.lede}>목표 → 변경한 운용 방식 → 검증 결과 → 결정 상태의 순서로 읽습니다. 확인된 과거 비교와 아직 답하지 못한 질문을 분리해 보여줍니다.</p></div><div className={styles.heroMeta}><strong>자료 기준 시각</strong><small>공개 {dateTime(progress?.research.published_at ?? null)}</small><small>화면 확인 {dateTime(progress?.observed_at ?? null)}</small><small>두 시각은 데이터가 만들어진 때와 페이지가 확인한 때를 뜻합니다.</small></div></section>{query.error && <div className={styles.alert} role="alert"><h2>연구 도구 요청 결과</h2><p>{query.error === "event-json" ? "시장 이벤트 JSON 배열 형식을 확인하세요." : "연구 도구 요청을 처리하지 못했습니다."} <Link className={styles.textLink} href="/research/lab">연구 도구로 이동</Link></p></div>}{availabilityNotice(progress)}<GoalSection progress={progress} /><ConditionsSection /><StudiesSection progress={progress} /><ObservationSection /></main>; }
