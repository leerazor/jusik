import Link from "next/link";
import { createMarketResearchRun } from "./actions";
import {
  getMarketReadiness,
  getMarketResearchRuns,
  type MarketReadiness,
  type MarketResearchRun,
} from "@/lib/marketResearch";

export const dynamic = "force-dynamic";

function readinessLabel(item: MarketReadiness): string {
  if (item.ready && item.simulated) return "합성 자료로 흐름 확인 가능";
  if (item.ready) return "실행 가능";
  return "필수 자료 부족";
}

function statusLabel(status: MarketResearchRun["status"]): string {
  return {
    queued: "대기", running: "실행 중", completed: "완료", insufficient: "검증 불충분", failed: "실패",
  }[status];
}

function stageLabel(stage: MarketResearchRun["stage"]): string {
  return { pilot: "1년 파일럿", final: "3년 최종", legacy: "기존 실행" }[stage];
}

export default async function MarketResearchPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const query = await searchParams;
  let readiness: MarketReadiness[] = [];
  let runs: MarketResearchRun[] = [];
  let unavailable = false;
  try { readiness = await getMarketReadiness(); } catch { unavailable = true; }
  try { runs = await getMarketResearchRuns(); } catch { unavailable = true; }
  const eligiblePilots = runs.filter((run) =>
    run.stage === "pilot" && run.status === "completed" &&
    run.result?.status === "ready" && run.result.completeness === "complete"
  );
  return (
    <main>
      <section className="intro research-intro">
        <div>
          <p className="eyebrow">POINT-IN-TIME MARKET RESEARCH</p>
          <h1>거래일 당시의 거래량 상위 종목 연구</h1>
          <p className="muted">각 거래일에 당시 확인 가능한 주식 전체에서 거래량 상위 20개를 고르고, 종가 신호 다음 거래일 시가로 체결하는 연구 흐름입니다.</p>
        </div>
        <div className="action-row"><Link className="secondary-button" href="/research">연구 개요</Link><Link className="secondary-button" href="/">계좌 현황</Link></div>
      </section>
      {query.error && <section className="notice" role="alert"><h2>시장 연구를 시작하지 못했습니다</h2><p>백엔드 상태와 기간을 확인한 뒤 다시 시도하세요.</p></section>}
      {unavailable && <section className="notice" role="alert"><h2>시장 연구 자료를 불러오지 못했습니다</h2><p>연구 백엔드 연결을 확인한 뒤 다시 시도하세요.</p></section>}
      <section className="research-step" aria-labelledby="readiness-title">
        <div className="step-heading"><p className="eyebrow">STEP 1</p><h2 id="readiness-title">실행 준비 상태</h2><p>자격 증명만으로 완전한 과거 자료가 있다고 판단하지 않습니다. 합성 자료는 화면과 계산 흐름만 확인합니다.</p></div>
        <div className="account-grid">
          {readiness.map((item) => <article className="account-card" key={item.market}><div className="account-heading"><strong>{item.market === "KR" ? "한국" : "미국"}</strong><span className={`status status-${item.ready ? "ok" : "error"}`}>{readinessLabel(item)}</span></div><ul>{item.capabilities.map((capability) => <li key={capability.name}>{capability.name}: {capability.detail}</li>)}</ul></article>)}
        </div>
      </section>
      <section className="research-step" aria-labelledby="run-title">
        <div className="step-heading"><p className="eyebrow">STEP 2</p><h2 id="run-title">결정론적 흐름 실행</h2><p>한국과 미국은 별도 원화 1억원으로 계산합니다. 미국은 시작 시점에만 달러로 환전하고 이후 달러 현금·거래와 원화 평가 곡선을 함께 기록합니다.</p></div>
        <form action={createMarketResearchRun} className="panel research-form"><label>시장<select name="market" defaultValue="KR"><option value="KR">한국</option><option value="US">미국</option></select></label><label>단계<select name="stage" defaultValue="pilot"><option value="pilot">1년 파일럿 · 검증</option><option value="final">3년 최종 · 완료 파일럿 필요</option></select></label><label>종료일<input name="end_date" type="date" defaultValue="2026-09-14" required /></label><label>참조할 완료 파일럿<select name="pilot_run_id" defaultValue=""><option value="">파일럿을 선택하세요 (최종 단계에서 필요)</option>{eligiblePilots.map((run) => <option value={run.id} key={run.id}>{run.request.market} · {run.request.end_date} · {run.id.slice(0, 8)}</option>)}</select></label><button type="submit">시장 연구 실행</button><p className="basis">파일럿은 종료일 기준 1년, 최종은 3년 전부터 서버가 기간을 계산합니다. 합성 실행은 인과 흐름 확인용이며 실제 수익률·주문 결과가 아닙니다.</p></form>
      </section>
      <section className="research-step" aria-labelledby="runs-title"><div className="step-heading"><p className="eyebrow">STEP 3</p><h2 id="runs-title">저장된 연구</h2></div><div className="panel">{runs.length === 0 ? <p className="empty-inline">저장된 실행이 없습니다.</p> : <div className="run-list">{runs.map((run) => <Link href={`/research/market/${run.id}`} className="run-row" key={run.id}><span><strong>{stageLabel(run.stage)} · {run.request.market} · {run.request.start_date}–{run.request.end_date}</strong><small>{run.created_at}</small></span><span className={`status status-${run.status}`}>{statusLabel(run.status)}</span></Link>)}</div>}</div></section>
    </main>
  );
}
