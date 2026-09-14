"use client";

import { useMemo, useState } from "react";
import { createMarketResearchRun } from "./actions";
import type { MarketResearchRun } from "@/lib/marketResearch";

export function StageForm({ pilots }: { pilots: MarketResearchRun[] }) {
  const [market, setMarket] = useState<"KR" | "US">("KR");
  const [stage, setStage] = useState<"pilot" | "final">("pilot");
  const marketPilots = useMemo(
    () => pilots.filter((run) => run.request.market === market),
    [market, pilots],
  );
  return (
    <form action={createMarketResearchRun} className="panel research-form">
      <label>시장<select name="market" value={market} onChange={(event) => setMarket(event.target.value as "KR" | "US")}><option value="KR">한국</option><option value="US">미국</option></select></label>
      <label>단계<select name="stage" value={stage} onChange={(event) => setStage(event.target.value as "pilot" | "final")}><option value="pilot">1년 파일럿 · 검증</option><option value="final">3년 최종 · 완료 파일럿 필요</option></select></label>
      <label>종료일<input name="end_date" type="date" defaultValue="2026-09-14" required /></label>
      <label>참조할 완료 파일럿<select name="pilot_run_id" defaultValue=""><option value="">파일럿을 선택하세요 (최종 단계에서 필요)</option>{marketPilots.map((run) => <option value={run.id} key={run.id}>{run.request.market} · {run.request.end_date} · {run.id.slice(0, 8)}</option>)}</select></label>
      <button type="submit">시장 연구 실행</button>
      <p className="basis">파일럿은 종료일 기준 1년, 최종은 3년 전부터 서버가 기간을 계산합니다. 합성 실행은 실제 수익률·주문 결과가 아닌 인과 흐름 확인용입니다.</p>
    </form>
  );
}
