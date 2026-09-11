import Link from "next/link";
import { getLatestDividendOverlay, researchAmount, type DividendOverlay } from "@/lib/research";

export const dynamic = "force-dynamic";

const scenarioLabels = {
  heldout: "선택 정책",
  equal_baseline: "동일 비중 추세 기준",
  cash_baseline: "현금 기준",
} as const;

function resultContent(result: DividendOverlay) {
  const download = (name: string) =>
    `/research/portfolio/dividends/download/${result.run_id}/${name}`;
  return (
    <>
      {!result.calculation_complete && (
        <section className="notice" role="alert"><h2>계산 입력 불완전</h2><p>{result.calculation_reasons.join(" · ")}</p></section>
      )}
      <section className="portfolio-metrics">
        {result.comparisons.map((item) => (
          <article className="metric-card" key={item.scenario}>
            <span>{scenarioLabels[item.scenario]}</span>
            <strong>{item.return_with_known_dividends_pct === null ? "계산 불가" : `${researchAmount(item.return_with_known_dividends_pct, 6)}%`}</strong>
            <small>기존 {researchAmount(item.baseline_return_pct, 6)}% · 증가 {item.increase_percentage_points === null ? "계산 불가" : `${researchAmount(item.increase_percentage_points, 6)}%p`}</small>
          </article>
        ))}
      </section>
      <section className="panel research-section">
        <div className="section-title simple"><h2>공식 근거 적용 범위</h2><span className="muted">후향 세전 연구</span></div>
        <p>현재 배당 revision {result.current_dividend_revision_count}건 중 필수 공식 근거가 모두 맞은 {result.eligible_dividend_count}건만 계산했습니다. 전체 제외 {result.excluded_dividend_count}건, 평가 기간 안 제외 {result.in_period_excluded_count}건입니다.</p>
        <p className="basis">계산 완전성과 배당 자료 coverage는 별개입니다. 이 결과는 확인된 일부 배당 기여분이며 전체 총수익률이 아닙니다.</p>
      </section>
      <section className="panel research-section">
        <div className="section-title simple"><h2>확인된 배당 권리</h2><span className="muted">임의 통화 반올림 없음</span></div>
        <div className="table-wrap"><table><thead><tr><th>정책</th><th>종목</th><th>배당락 개장 (UTC)</th><th>지급 경계 (UTC)</th><th>권리 수량</th><th>세전 금액</th></tr></thead><tbody>
          {result.entitlements.map((item) => <tr key={`${item.scenario}-${item.event_id}`}><td>{scenarioLabels[item.scenario]}</td><td>{item.symbol}</td><td>{item.ex_open_at}</td><td>{item.payment_boundary_at}</td><td>{item.entitled_quantity}</td><td>{researchAmount(item.gross_native, 8)} {item.currency}</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="panel research-section">
        <div className="section-title simple"><h2>원화 환산 근거</h2><span className="muted">최종 평가 시점</span></div>
        <div className="table-wrap"><table><thead><tr><th>정책</th><th>배당 기여</th><th>USD/KRW</th><th>관측일</th><th>사용 가능 시각 (UTC)</th><th>revision</th></tr></thead><tbody>
          {result.equity.filter((point, index, rows) => index === rows.findLastIndex((candidate) => candidate.scenario === point.scenario)).map((point) => <tr key={point.scenario}><td>{scenarioLabels[point.scenario]}</td><td>{point.dividend_contribution_krw === null ? "계산 불가" : `${researchAmount(point.dividend_contribution_krw, 2)}원`}</td><td>{point.fx_rate ?? "불필요/결측"}</td><td>{point.fx_observed_on ?? "-"}</td><td>{point.fx_available_at ?? "-"}</td><td>{point.fx_revision ?? "-"}</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="panel research-section limitations">
        <div className="section-title simple"><h2>가정과 한계</h2></div>
        <ul>{result.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
        <p className="basis">세금, 재투자, 환전, 이자와 환전 비용을 계산하지 않습니다. 지급 경계는 실제 입금 시각이 아니라 지급일 다음 현지 자정이라는 표시 관례입니다. 자동 원장 반영과 주문은 하지 않습니다.</p>
      </section>
      <section className="panel research-section">
        <div className="section-title simple"><h2>산출물 내려받기</h2><span className="muted">실행 {result.run_id.slice(0, 10)}</span></div>
        <div className="artifact-links">{[...result.artifacts, "manifest.json"].map((name) => <a className="secondary-button" href={download(name)} key={name}>{name}</a>)}</div>
      </section>
    </>
  );
}

export default async function DividendOverlayPage() {
  let result: DividendOverlay | null = null;
  try { result = await getLatestDividendOverlay(); } catch { /* rendered below */ }
  return (
    <main>
      <header className="research-result-header"><Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">검증된 배당 기여분</span></Link><div className="action-row"><Link className="secondary-button" href="/research/portfolio">포트폴리오</Link><Link className="secondary-button" href="/research/actions">기업행동</Link><span className="badge">세전 후향 연구 · 실제 주문 없음</span></div></header>
      <section className="intro research-intro"><div><p className="eyebrow">DIVIDEND OVERLAY</p><h1>공식 근거가 맞은 배당만 더해 보기</h1><p className="muted">고정된 포트폴리오 거래와 평가액에 검증된 배당 기여분만 별도 표시합니다.</p></div></section>
      {result ? resultContent(result) : <section className="panel pending-panel"><h2>배당 overlay 결과가 없습니다</h2><p className="muted">독립 검증과 산출물 생성이 끝난 뒤 표시됩니다.</p></section>}
    </main>
  );
}
