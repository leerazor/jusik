import type { ReactNode } from "react";
import Link from "next/link";
import { OperationsRefresh } from "@/app/research/lab/operations-refresh";
import {
  compareDecimal,
  getResearchProgress,
  type Comparison,
  type ResearchProgress,
  type RunnerTask,
  type Study,
} from "@/lib/research-progress";
import { candidateRuleForComparison, getStudyNarrative } from "@/lib/research-narrative";
import styles from "./progress.module.css";

export const dynamic = "force-dynamic";

const statusLabels: Record<string, string> = {
  queued: "대기",
  running: "실행 중",
  completed: "완료",
  blocked: "차단됨",
  failed: "실패",
  interrupted: "중단됨",
};

function statusLabel(status: string): string {
  return statusLabels[status] ?? "상태 확인 필요";
}

function availabilityLabel(availability: ResearchProgress["runner"]["availability"]): string {
  return { available: "사용 가능", unavailable: "사용할 수 없음", invalid: "검증 실패" }[availability];
}

function formatDateTime(value: string | null): string {
  if (!value) return "확인할 수 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "확인할 수 없음";
  return `${date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}

type ExpandedDecimal = {
  negative: boolean;
  digits: string;
  decimalPosition: number;
};

function expandDecimal(value: string): ExpandedDecimal | null {
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return null;
  const [, sign, whole, fraction = "", exponentText = "0"] = match;
  const rawDigits = `${whole}${fraction}`;
  if (!/[1-9]/.test(rawDigits)) {
    return { negative: false, digits: "0", decimalPosition: 1 };
  }
  const exponent = Number(exponentText);
  if (!Number.isSafeInteger(exponent)) return null;
  const digits = rawDigits.replace(/^0+(?=\d)/, "");
  const leadingZeros = rawDigits.length - rawDigits.replace(/^0+/, "").length;
  return {
    negative: sign === "-" && /[1-9]/.test(digits),
    digits,
    decimalPosition: whole.length + exponent - leadingZeros,
  };
}

function groupInteger(value: string): string {
  return value.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function formatDecimal(value: string, digits = 2): string {
  const expanded = expandDecimal(value);
  if (!expanded) return "—";
  const point = expanded.decimalPosition;
  let whole: string;
  let fraction: string;
  if (point <= 0) {
    whole = "0";
    fraction = `${"0".repeat(Math.max(0, -point))}${expanded.digits}`;
  } else if (point >= expanded.digits.length) {
    whole = `${expanded.digits}${"0".repeat(point - expanded.digits.length)}`;
    fraction = "";
  } else {
    whole = expanded.digits.slice(0, point);
    fraction = expanded.digits.slice(point);
  }
  const shownFraction = digits > 0
    ? fraction.slice(0, digits).padEnd(digits, "0")
    : "";
  const suffix = shownFraction ? `.${shownFraction}` : "";
  return `${expanded.negative ? "-" : ""}${groupInteger(whole)}${suffix}`;
}

function formatPercent(value: string): string {
  return `${formatDecimal(value)}%`;
}

function formatKrw(value: string): string {
  return `${formatDecimal(value, 0)}원`;
}

function formatCount(value: number): string {
  return value.toLocaleString("ko-KR");
}

function formatDuration(seconds: number): string {
  if (seconds >= 3600 && seconds % 3600 === 0) return `${seconds / 3600}시간`;
  if (seconds >= 60) return `${Math.round(seconds / 60)}분`;
  return `${seconds}초`;
}

function stateClass(value: string): string {
  if (value === "available" || value === "active") return styles.stateGood;
  if (value === "unavailable" || value === "invalid" || value === "inactive") return styles.stateBad;
  return styles.stateUnknown;
}

function MetricValue({ label, value, kind }: { label: string; value: string; kind: "percent" | "currency" | "count" }) {
  const display = kind === "percent" ? formatPercent(value) : kind === "currency" ? formatKrw(value) : formatDecimal(value, 0);
  return <div><dt>{label}</dt><dd>{display}</dd></div>;
}

function ComparisonPanel({ study, comparison }: { study: Study; comparison: Comparison }) {
  const narrative = getStudyNarrative(study);
  const adverse: string[] = [];
  if (compareDecimal(comparison.candidate.net_return_pct, comparison.baseline.net_return_pct) === -1) adverse.push("수익률 하락");
  if (compareDecimal(comparison.candidate.max_drawdown_pct, comparison.baseline.max_drawdown_pct) === 1) adverse.push("낙폭 확대");
  if (compareDecimal(comparison.candidate.total_cost_krw, comparison.baseline.total_cost_krw) === 1) adverse.push("비용 증가");
  if (compareDecimal(comparison.candidate.annual_turnover_pct, comparison.baseline.annual_turnover_pct) === 1) adverse.push("회전율 증가");
  const cashLabel = comparison.cash_statistic === "mean" ? "평균 현금 비중" : "중앙값 현금 비중";
  return (
    <section className={styles.featuredPanel} aria-labelledby="featured-title">
      <div className={styles.sectionHeading}>
        <div><p className={styles.kicker}>대표 비교 · {study.title}</p><h2 id="featured-title">같은 조건에서 두 방식을 비교했어요</h2><p className={styles.muted}>{comparison.period_start}–{comparison.period_end} · 비용 {comparison.cost_multiplier}배 · {cashLabel} · 낙폭 기준 {comparison.drawdown_basis === "close_nav" ? "종가 평가액" : "전체 관측 평가액"}</p></div>
        <Link className={styles.reportLink} href={`/research/history/download/${study.report_artifact_sha256}`}>검증 보고서 열기<span aria-hidden="true"> ↗</span></Link>
      </div>
      <p className={styles.featuredConclusion}>{narrative?.conclusion ?? "연구 설명의 식별 정보가 맞지 않아 결론을 표시하지 않습니다. 검증된 수치와 보고서는 확인할 수 있습니다."}</p>
      <div className={styles.strategyCards}>
        {[{ label: "기존 방식", metrics: comparison.baseline }, { label: "시험한 방식", metrics: comparison.candidate }].map((item) => (
          <article className={styles.strategyCard} key={item.label}>
            <span className={styles.cardEyebrow}>{item.label}</span><h3>{item.metrics.label}</h3>
            <dl className={styles.metricGrid}>
              <MetricValue label="기간 누적 수익률" value={item.metrics.net_return_pct} kind="percent" />
              <MetricValue label={cashLabel} value={item.metrics.cash_pct} kind="percent" />
              <MetricValue label="가장 크게 하락한 폭" value={item.metrics.max_drawdown_pct} kind="percent" />
              <MetricValue label="거래한 날" value={String(item.metrics.trade_days)} kind="count" />
              <MetricValue label="총 비용" value={item.metrics.total_cost_krw} kind="currency" />
              <MetricValue label="연환산 회전율" value={item.metrics.annual_turnover_pct} kind="percent" />
            </dl>
          </article>
        ))}
      </div>
      <p className={styles.metricExplainer}>수익률은 이 비교 기간 전체의 누적 변화이며 연환산이 아닙니다. 최대 낙폭은 평가액 고점 뒤 가장 크게 줄어든 폭입니다. 현금 비중은 기간 중 현금의 {comparison.cash_statistic === "mean" ? "평균" : "중앙값"}이고, 거래일은 실제 주문 횟수가 아니라 거래가 발생한 날짜 수입니다. 비용과 회전율이 함께 늘면 수익률만으로 개선이라 할 수 없습니다. {comparison.drawdown_basis === "close_nav" ? "종가 평가액만으로 계산한 낙폭은 모든 관측 시점의 목표 충족을 증명하지 않습니다." : "모든 관측 평가액 기준이라도 이 과거 비교의 범위 안에서만 읽습니다."}</p>
      <div className={adverse.length > 0 ? styles.changeWarning : styles.changeNote} role={adverse.length > 0 ? "status" : undefined}>
        <strong>{adverse.length > 0 ? "주의할 변화" : "해석할 때 함께 볼 점"}</strong>
        <span>{adverse.length > 0 ? `${adverse.join(" · ")} — 모든 지표가 개선된 것은 아닙니다.` : "수익률·현금·낙폭뿐 아니라 비용과 회전율도 함께 봐야 합니다."}</span>
      </div>
    </section>
  );
}

function StatusCard({ title, availability, children }: { title: string; availability: "available" | "unavailable" | "invalid"; children: ReactNode }) {
  return <article className={styles.statusCard}><div className={styles.statusCardHeading}><h3>{title}</h3><span className={`${styles.statusPill} ${stateClass(availability)}`}>{availabilityLabel(availability)}</span></div>{children}</article>;
}

function RunnerOverview({ progress }: { progress: ResearchProgress }) {
  const { runner } = progress;
  const hasCurrent = runner.current !== null || (runner.counts?.running ?? 0) > 0 || runner.tasks.some((task) => task.status === "running");
  const headline = runner.availability !== "available" ? "상태 확인 불가"
    : runner.paused === true ? "일시정지"
      : runner.paused === null || runner.service === "unknown" ? "상태 확인 불가"
        : hasCurrent ? runner.service === "active" ? "자동 개발 진행 중" : "실행 확인 필요"
          : runner.timer === "unknown" ? "상태 확인 불가"
            : runner.timer === "active" ? "자동 실행 대기" : "실행 확인 필요";
  return (
    <section className={styles.overviewSection} aria-labelledby="overview-title">
      <div className={styles.runtimeSummary}>
        <p className={styles.kicker}>자동 개발 현재 상태</p>
        <h2 id="overview-title">{headline}</h2>
        {runner.availability === "available" && runner.current && <p className={styles.currentTitle}>기록된 작업 · <strong>{runner.current.title}</strong></p>}
        <p className={styles.muted}>{headline === "자동 개발 진행 중" ? "서비스 활성 상태와 실행 중 작업 기록이 확인되었습니다." : headline === "일시정지" ? "일시정지가 설정되어 있습니다. 아래에서 남은 작업을 확인하세요." : headline === "자동 실행 대기" ? "실행 중인 작업 기록이 없고 자동 실행 타이머가 활성 상태입니다." : "현재 실행 여부를 확정할 수 없습니다. 아래 진단 상태를 확인하세요."}</p>
        <small>마지막 확인 {formatDateTime(progress.observed_at)} · 작업 기록만으로 실제 실행을 보장하지 않습니다.</small>
      </div>
      <details className={styles.diagnostics}><summary>실행기·연구 자료 진단 상태</summary>
      <div className={styles.statusGrid}>
        <StatusCard title="자동 연구 실행기" availability={runner.availability}>
          <dl className={styles.compactDetails}><div><dt>서비스</dt><dd className={stateClass(runner.service)}>{runner.service === "active" ? "활성" : runner.service === "inactive" ? "비활성" : "확인 불가"}</dd></div><div><dt>타이머</dt><dd className={stateClass(runner.timer)}>{runner.timer === "active" ? "활성" : runner.timer === "inactive" ? "비활성" : "확인 불가"}</dd></div><div><dt>일시정지</dt><dd>{runner.paused === null ? "확인 불가" : runner.paused ? "예" : "아니오"}</dd></div><div><dt>마지막 기록</dt><dd>{formatDateTime(runner.recorded_at)}</dd></div></dl>
        </StatusCard>
        <StatusCard title="연구 카탈로그" availability={progress.research.availability}>
          <dl className={styles.compactDetails}><div><dt>공개 시각</dt><dd>{formatDateTime(progress.research.published_at)}</dd></div><div><dt>검증 연구</dt><dd>{progress.research.availability === "available" ? `${formatCount(progress.research.studies.length)}개` : "표시하지 않음"}</dd></div></dl>
        </StatusCard>
      </div>
      </details>
      <div className={styles.policyAndCounts}>
        <article className={styles.policyCard}><div className={styles.cardHeading}><h3>실행 조건</h3><span>운영 기준</span></div>{runner.policy ? <dl className={styles.policyGrid}><div><dt>작업별 시간 제한</dt><dd>{formatDuration(runner.policy.task_timeout_seconds)} <small>전체 연구 제한 아님</small></dd></div><div><dt>전체 종료 시각</dt><dd>없음</dd></div><div><dt>대기 간격</dt><dd>{formatDuration(runner.policy.cooldown_seconds)}</dd></div><div><dt>오늘 실행</dt><dd>{formatCount(runner.policy.launches_today)}{runner.policy.daily_launch_limit === null ? " · 일일 상한 없음" : ` / ${formatCount(runner.policy.daily_launch_limit)}`}</dd></div><div><dt>계획 기능</dt><dd>{runner.policy.planning_enabled ? "사용" : "사용 안 함"}</dd></div></dl> : <p className={styles.emptyInline}>실행 조건을 확인할 수 없습니다.</p>}</article>
        <article className={styles.countCard}><div className={styles.cardHeading}><h3>등록된 자동 개발 작업</h3><span>전체 프로젝트 완료율이 아님</span></div>{runner.counts ? <div className={styles.countGrid}>{(["queued", "running", "completed", "blocked", "failed", "interrupted", "other"] as const).map((key) => <div key={key}><span>{key === "queued" ? "대기" : key === "running" ? "실행 중" : key === "completed" ? "완료" : key === "blocked" ? "차단" : key === "failed" ? "실패" : key === "interrupted" ? "중단" : "기타"}</span><strong>{formatCount(runner.counts![key])}</strong></div>)}</div> : <p className={styles.emptyInline}>작업 수를 확인할 수 없습니다.</p>}</article>
      </div>
    </section>
  );
}

function taskGroup(task: RunnerTask, currentId: string | null): "current" | "waiting" | "blocked" | "interrupted" | "completed" | "other" {
  if (task.task_id === currentId || task.status === "running") return "current";
  if (task.status === "queued") return "waiting";
  if (task.status === "blocked") return "blocked";
  if (task.status === "interrupted") return "interrupted";
  if (task.status === "completed") return "completed";
  return "other";
}

function TaskItem({ task, tasks }: { task: RunnerTask; tasks: RunnerTask[] }) {
  const dependency = task.depends_on ? tasks.find((candidate) => candidate.task_id === task.depends_on) : null;
  return <li className={styles.taskItem}><div className={styles.taskItemTop}><strong>{task.title}</strong><span className={styles.taskStatus}>{task.status === "running" ? "실행 중 기록" : statusLabel(task.status)}</span></div>{task.depends_on && <small>선행: {dependency?.title ?? "선행 작업 정보 확인 필요"}</small>}<small>갱신 {formatDateTime(task.updated_at)}{task.next_allowed_at ? ` · 재개 가능 ${formatDateTime(task.next_allowed_at)}` : ""}</small></li>;
}

function QueueSection({ progress }: { progress: ResearchProgress }) {
  const runner = progress.runner;
  const currentId = runner.current?.task_id ?? null;
  const groups: Array<{ key: ReturnType<typeof taskGroup>; label: string; tasks: RunnerTask[] }> = [
    { key: "current", label: "현재 작업 기록", tasks: [] },
    { key: "waiting", label: "대기 중", tasks: [] },
    { key: "blocked", label: "차단됨", tasks: [] },
    { key: "interrupted", label: "중단됨", tasks: [] },
    { key: "completed", label: "최근 완료", tasks: [] },
    { key: "other", label: "기타 상태", tasks: [] },
  ];
  for (const task of runner.tasks) groups.find((group) => group.key === taskGroup(task, currentId))?.tasks.push(task);
  groups.find((group) => group.key === "completed")?.tasks.sort((left, right) => right.updated_at.localeCompare(left.updated_at));
  const currentMissing = runner.current && !groups[0].tasks.some((task) => task.task_id === runner.current?.task_id);
  return (
    <section className={styles.queueSection} aria-labelledby="queue-title">
      <div className={styles.sectionHeading}><div><p className={styles.kicker}>작업 흐름</p><h2 id="queue-title">자동 연구 작업 목록</h2><p className={styles.muted}>표시 순서: 현재 실행 · 대기 · 차단 · 중단 · 최근 완료</p></div>{runner.truncated && <span className={styles.truncated}>최근 작업 일부만 표시</span>}</div>
      {runner.availability !== "available" ? <div className={styles.unavailableBox}>실행기 작업 목록을 표시할 수 없습니다. 사용 불가나 검증 실패를 대기 상태로 해석하지 않습니다.</div> : <div className={styles.queueGrid}>{groups.map((group) => {
        const visibleTasks = group.key === "completed" ? group.tasks.slice(0, 6) : group.tasks;
        const remainingTasks = group.key === "completed" ? group.tasks.slice(6) : [];
        return <article className={styles.queueGroup} key={group.key}>
          <div className={styles.queueGroupHeading}><h3>{group.label}</h3><span>{formatCount(group.tasks.length + (group.key === "current" && currentMissing ? 1 : 0))}</span></div>
          {group.key === "current" && currentMissing && runner.current && <ul className={styles.taskList}><li className={styles.taskItem}><div className={styles.taskItemTop}><strong>{runner.current.title}</strong><span className={styles.taskStatus}>실행 중 기록</span></div><small>시작 {formatDateTime(runner.current.started_at)}</small></li></ul>}
          {visibleTasks.length > 0 && <ul className={styles.taskList}>{visibleTasks.map((task) => <TaskItem key={task.task_id} task={task} tasks={runner.tasks} />)}</ul>}
          {remainingTasks.length > 0 && <details className={styles.completedDetails}><summary>완료 작업 {formatCount(remainingTasks.length)}개 더 보기</summary><ul className={styles.taskList}>{remainingTasks.map((task) => <TaskItem key={task.task_id} task={task} tasks={runner.tasks} />)}</ul></details>}
          {group.tasks.length === 0 && !(group.key === "current" && currentMissing) && <p className={styles.emptyInline}>해당 작업 없음</p>}
        </article>;
      })}</div>}
    </section>
  );
}

function StudiesSection({ progress }: { progress: ResearchProgress }) {
  const studies = [...progress.research.studies].sort((left, right) => right.published_at.localeCompare(left.published_at));
  const comparisonTotal = studies.reduce((total, study) => total + study.comparisons.length, 0);
  return <section className={styles.studiesSection} aria-labelledby="studies-title"><div className={styles.sectionHeading}><div><p className={styles.kicker}>{progress.research.availability === "available" ? `공개 연구 ${studies.length}개 · 비교 ${comparisonTotal}개` : "연구 자료 확인 필요"}</p><h2 id="studies-title">연구 질문과 결과</h2><p className={styles.muted}>질문과 결론부터 읽으세요. 원본 보고서는 바로 열 수 있고, 계산 조건과 모든 수치는 펼쳐 볼 수 있습니다.</p></div><Link className={styles.textLink} href="/research/history">전체 연구 이력 보기</Link></div>{progress.research.availability !== "available" ? <div className={styles.unavailableBox}>검증된 연구 카탈로그를 표시할 수 없습니다.</div> : studies.length === 0 ? <div className={styles.emptyPanel}>공개된 연구가 아직 없습니다.</div> : <div className={styles.studyGrid}>{studies.map((study) => { const narrative = getStudyNarrative(study); return <article className={styles.studyCard} id={`study-${study.id}`} key={study.id}><div className={styles.studyCardHeading}><div><span className={styles.cardEyebrow}>연구 질문</span><h3>{narrative?.question ?? study.title}</h3></div><Link className={styles.reportLink} aria-label={`${study.title} 원본 보고서`} href={`/research/history/download/${study.report_artifact_sha256}`}>보고서 ↗</Link></div>{narrative ? <><p className={styles.studyQuestion}>{study.title}</p><p className={styles.decisionNote}><strong>확인한 결론</strong> {narrative.conclusion}</p><p className={styles.keyLimit}><strong>꼭 알아둘 한계</strong> {narrative.limitations[0]}</p><details className={styles.studyDisclosure}><summary>바꾼 규칙과 나머지 한계 보기</summary><div className={styles.narrativeGrid}><div><strong>관련 목표</strong><p>{narrative.relatedGoals.join(" · ")}</p></div><div><strong>기존 방식</strong><p>{narrative.baselineRules.join(" · ")}</p></div><div><strong>시험 방식</strong><p>{narrative.candidateRules.join(" · ")}</p></div><div><strong>고정 조건</strong><p>{narrative.fixedConditions.join(" · ")}</p></div></div><p className={styles.decisionNote}>재조정은 보유 종목에 넣는 돈의 비중을 다시 맞추는 일입니다. 연 변동성 목표는 연간 수익률의 흔들림을 조절하는 목표이며, 약속된 수익률이나 손실 한도가 아닙니다.</p><p className={styles.decisionNote}>{narrative.limitations.slice(1).join(" ")}</p></details></> : <div className={styles.unavailableBox}>연구 설명을 확인할 수 없습니다. API가 제공한 제목·수치·보고서 링크는 유지합니다.</div>}<p className={styles.studyMetaLine}>공개 {formatDateTime(study.published_at)} · {study.universe_symbols.length}종목 · 과거 가격만 · 배당·세금 제외</p><details className={styles.studyDisclosure}><summary>모든 비교 표 보기 · {study.comparisons.length}개</summary><div className={styles.comparisonDetails}>{study.comparisons.length === 0 ? <p className={styles.emptyInline}>비교 조건 없음</p> : study.comparisons.map((comparison) => { const candidateRule = candidateRuleForComparison(study, comparison.id); return <details key={comparison.id}><summary><span>{comparison.period_start}–{comparison.period_end} · 비용 {comparison.cost_multiplier}배 · 현금 {comparison.cash_statistic === "mean" ? "평균" : "중앙값"}</span><strong>{comparison.baseline.label} ↔ {comparison.candidate.label}</strong></summary>{candidateRule && <p className={styles.comparisonRule}><strong>후보 규칙:</strong> {candidateRule.label} · {candidateRule.mapping}</p>}<div className={styles.tableWrap}><table><caption>{comparison.id} 비교</caption><thead><tr><th scope="col">지표</th><th scope="col">기준선 · {comparison.baseline.label}</th><th scope="col">후보 · {comparison.candidate.label}</th></tr></thead><tbody><tr><th scope="row">기간 누적 수익률</th><td>{formatPercent(comparison.baseline.net_return_pct)}</td><td>{formatPercent(comparison.candidate.net_return_pct)}</td></tr><tr><th scope="row">현금 비중 ({comparison.cash_statistic === "mean" ? "평균" : "중앙값"})</th><td>{formatPercent(comparison.baseline.cash_pct)}</td><td>{formatPercent(comparison.candidate.cash_pct)}</td></tr><tr><th scope="row">최대 낙폭 ({comparison.drawdown_basis === "close_nav" ? "종가 평가액" : "전체 관측 평가액"})</th><td>{formatPercent(comparison.baseline.max_drawdown_pct)}</td><td>{formatPercent(comparison.candidate.max_drawdown_pct)}</td></tr><tr><th scope="row">최대 레버리지</th><td>{formatPercent(comparison.baseline.max_leverage_pct)}</td><td>{formatPercent(comparison.candidate.max_leverage_pct)}</td></tr><tr><th scope="row">연환산 회전율</th><td>{formatPercent(comparison.baseline.annual_turnover_pct)}</td><td>{formatPercent(comparison.candidate.annual_turnover_pct)}</td></tr><tr><th scope="row">총 비용</th><td>{formatKrw(comparison.baseline.total_cost_krw)}</td><td>{formatKrw(comparison.candidate.total_cost_krw)}</td></tr><tr><th scope="row">거래일</th><td>{formatCount(comparison.baseline.trade_days)}일</td><td>{formatCount(comparison.candidate.trade_days)}일</td></tr></tbody></table></div><p className={styles.comparisonBasis}>기간 {comparison.period_start}–{comparison.period_end} · 비용 {comparison.cost_multiplier}배 · 현금은 UTC 하루 마지막 평가액의 {comparison.cash_statistic === "mean" ? "평균" : "중앙값"} · 낙폭은 {comparison.drawdown_basis === "close_nav" ? "종가 평가액" : "모든 관측 평가액"}</p></details>; })}</div></details></article>; })}</div>}</section>;
}

function FeaturedSection({ progress }: { progress: ResearchProgress }) {
  const featuredId = progress.research.featured_comparison_id;
  const result = featuredId ? progress.research.studies.flatMap((study) => study.comparisons.map((comparison) => ({ study, comparison }))).find((item) => item.comparison.id === featuredId) : null;
  if (progress.research.availability !== "available") return <section className={styles.featuredSection}><div className={styles.sectionHeading}><div><p className={styles.kicker}>대표 비교</p><h2>같은 조건의 기준 비교</h2></div></div><div className={styles.unavailableBox}>연구 상태가 {progress.research.availability === "invalid" ? "검증되지 않아" : "사용할 수 없어"} 대표 비교를 표시할 수 없습니다.</div></section>;
  if (!result) return <section className={styles.featuredSection}><div className={styles.sectionHeading}><div><p className={styles.kicker}>대표 비교</p><h2>같은 조건의 기준 비교</h2></div></div><div className={styles.emptyPanel}>대표 비교가 아직 공개되지 않았습니다.</div></section>;
  return <section className={styles.featuredSection}><ComparisonPanel study={result.study} comparison={result.comparison} /></section>;
}

function ProgressPurpose() {
  return <p className={styles.readingGuide}><strong>읽는 방법</strong> 기존 방식과 시험한 방식을 나란히 보세요. 수익이 늘어도 손실 위험이나 비용이 커질 수 있습니다. 모두 과거 자료를 이용한 비교이며 투자 추천은 아닙니다.</p>;
}

export default async function ResearchProgressPage() {
  let progress: ResearchProgress | null = null;
  try {
    progress = await getResearchProgress();
  } catch {
    progress = null;
  }

  return (
    <main className={styles.progressMain}>
      <OperationsRefresh />
      <section className={styles.hero}>
        <div><p className={styles.kicker}>과거 자료에서 확인한 것</p><h1>연구 결과</h1><p className={styles.heroCopy}>무엇을 바꿨고, 어떤 차이가 있었을까요?<br />좋아진 점과 아직 믿기 어려운 점을 함께 읽습니다.</p></div>
        <div className={styles.refreshState}><span className={styles.autoDot} aria-hidden="true" />자동 새로고침 · 10초{progress && <small>마지막 확인 {formatDateTime(progress.observed_at)}</small>}</div>
      </section>
      {!progress ? <section className={styles.unavailableBox} role="alert"><h2>진행 현황을 불러올 수 없습니다</h2><p>연구 진행 API가 아직 연결되지 않았거나 응답을 검증하지 못했습니다. 자동 실행 중이나 정상 대기로 해석하지 않습니다.</p></section> : <><ProgressPurpose /><FeaturedSection progress={progress} /><StudiesSection progress={progress} /><details className={styles.operationsDetails}><summary>운영 상세 · 자동 실행기와 작업 대기열</summary><RunnerOverview progress={progress} /><QueueSection progress={progress} /></details><footer className={styles.footer}>모든 연구는 과거 가격 데이터만 사용하며 배당과 세금을 포함하지 않습니다. 회고용으로 재사용된 자료이고 시점 검증 전이므로 미래 성과를 입증하지 않습니다. · <Link href="/research/history">연구 이력과 보고서</Link></footer></>}
    </main>
  );
}
