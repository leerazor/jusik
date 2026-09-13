import Link from "next/link";
import { getResearchProgress, type Comparison, type ResearchProgress } from "@/lib/research-progress";
import { researchAmount } from "@/lib/research";
import { OperationsRefresh } from "./lab/operations-refresh";

export const dynamic = "force-dynamic";

function percent(value: string): string { return `${researchAmount(value, 2)}%`; }
function statusText(progress: ResearchProgress | null): string {
  if (!progress) return "확인할 수 없음";
  if (progress.research.availability === "invalid") return "검증되지 않음";
  if (progress.research.availability === "unavailable") return "사용할 수 없음";
  return progress.research.studies.length > 0 ? "과거 비교 자료 있음" : "아직 공개 자료 없음";
}
function featured(progress: ResearchProgress): { comparison: Comparison; title: string } | null {
  const id = progress.research.featured_comparison_id;
  if (!id) return null;
  for (const study of progress.research.studies) {
    const comparison = study.comparisons.find((item) => item.id === id);
    if (comparison) return { comparison, title: study.title };
  }
  return null;
}

export default async function ResearchHubPage() {
  let progress: ResearchProgress | null = null;
  try { progress = await getResearchProgress(); } catch { progress = null; }
  const representative = progress ? featured(progress) : null;

  return (
    <main className="research-hub">
      <OperationsRefresh />
      <header className="research-header">
        <Link href="/" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">투자 판단 자료</span></Link>
        <nav className="research-nav" aria-label="연구 메뉴">
          <Link href="/research" aria-current="page">연구 개요</Link>
          <Link href="/research/progress">진행·성과</Link>
          <Link href="/research/forward">가상 관찰</Link>
          <Link href="/research/history">개발 기록</Link>
          <Link href="/research/lab">연구 도구</Link>
        </nav>
      </header>

      <section className="hub-hero">
        <div>
          <p className="eyebrow">INVESTOR RESEARCH</p>
          <h1>이 전략을 계속 믿어도 될까?</h1>
          <p className="hub-lede">1억원을 여러 종목에 나누고, 불필요한 현금과 잦은 거래를 줄이는 방법을 검증합니다. 이 화면은 결론을 정해두지 않고 지금 확인된 것과 아직 모르는 것을 함께 보여줍니다.</p>
        </div>
        <div className="hub-status"><span className="status">현재 단계</span><strong>{statusText(progress)}</strong><small>{progress ? `기준 시각 ${new Date(progress.observed_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}` : "진행 API 응답 없음"}</small></div>
      </section>

      <section className="story-grid" aria-label="투자 연구 판단 순서">
        <article className="story-card story-card-active"><span className="story-number">01</span><h2>목표</h2><p>최고 평가액에서 20% 하락하는 상황을 목표 한도로 삼습니다. 손실을 보장하는 자동 안전장치는 아닙니다.</p><strong>저회전·낮은 불필요 현금</strong></article>
        <article className="story-card"><span className="story-number">02</span><h2>확인한 증거</h2><p>과거 자료 비교와 새로운 시세를 보는 가상 관찰은 서로 다른 증거입니다. 후보가 곧 채택안은 아닙니다.</p><Link href="/research/progress">같은 조건 비교 보기 →</Link></article>
        <article className="story-card"><span className="story-number">03</span><h2>다음 판단</h2><p>위험·비용을 감안한 개선이 독립 검증에서도 유지되는지 확인해야 합니다. 아니면 후보를 보류합니다.</p><Link href="/research/forward">가상 관찰 범위 보기 →</Link></article>
      </section>

      <section className="hub-section" aria-labelledby="evidence-title">
        <div className="section-heading-row"><div><p className="eyebrow">EVIDENCE, NOT PROMISE</p><h2 id="evidence-title">현재 자료가 말해주는 범위</h2></div><Link className="text-link" href="/research/progress">전체 진행 현황</Link></div>
        {representative ? <div className="evidence-card"><div><span className="status">대표 비교 · 순위 아님</span><h3>{representative.title}</h3><p className="muted">{representative.comparison.period_start}–{representative.comparison.period_end} · {representative.comparison.cash_statistic === "mean" ? "현금 평균" : "현금 중앙값"} · 비용 {representative.comparison.cost_multiplier}배</p></div><div className="evidence-metrics"><div><small>후보 누적 수익률</small><strong>{percent(representative.comparison.candidate.net_return_pct)}</strong></div><div><small>후보 최대 하락</small><strong>{percent(representative.comparison.candidate.max_drawdown_pct)}</strong></div><div><small>후보 현금</small><strong>{percent(representative.comparison.candidate.cash_pct)}</strong></div></div></div> : <div className="notice" role="status"><h3>대표 비교를 표시할 수 없습니다</h3><p>자료 없음·사용 불가·검증 실패를 성과 0으로 바꾸지 않았습니다. 진행 화면에서 원인을 확인할 수 있습니다.</p></div>}
        <div className="limits-grid"><div><h3>이 자료로 알 수 있는 것</h3><p>같은 종목·기간·비용 조건에서 기준 방식과 변경안을 비교한 결과입니다. 누적 수익률은 연환산 수익률이 아닙니다.</p></div><div><h3>아직 알 수 없는 것</h3><p>배당·세금 제외, 회고용 데이터 재사용, 시점 검증 전 자료입니다. 단순 투자안과의 독립 검증도 아직 필요합니다.</p></div></div>
      </section>

      <section className="hub-section next-decision" aria-labelledby="next-title"><div><p className="eyebrow">NEXT DECISION</p><h2 id="next-title">계속할 이유는 다음 검증에서 생깁니다</h2><p>좋은 과거 결과만으로 실거래 적합성이나 미래 수익을 증명할 수 없습니다. 비용과 위험을 함께 본 뒤, 독립된 단순 기준과 새로운 기간에서 같은 결론이 나오는지 확인하세요.</p></div><div className="hub-actions"><Link className="primary-link" href="/research/progress">근거 읽기</Link><Link className="secondary-button" href="/research/lab">상세 도구 열기</Link></div></section>

      <footer className="hub-footer"><span>연구는 실거래가 아니며 브로커 주문을 만들지 않습니다.</span><Link href="/research-guide.html">사용 안내</Link><Link href="/">실계좌 조회</Link></footer>
    </main>
  );
}
