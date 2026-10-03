"use client";

import { useActionState, useState, useTransition } from "react";
import { refreshApprovedReadiness, saveApprovedUniverse, type SaveState } from "./actions";
import type { ApprovedInstrument, ApprovedReadiness, ApprovedUniverse } from "./contract";
import styles from "./page.module.css";

function line(item: ApprovedInstrument): string {
  return item.market === "KR" ? `KR,${item.symbol}` : `US,${item.exchange},${item.symbol}`;
}

function normalizedLineEndings(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}

const priceLabel: Record<ApprovedReadiness["instruments"][number]["price"]["status"], string> = {
  missing: "수집 기록 없음", success: "최근 수집 성공", stale: "이전 수집 자료 · 최근 수집 실패",
  error: "수집 오류", unavailable: "조회 불가",
};

export function ApprovedUniverseEditor({ initial, initialReadiness }: { initial: ApprovedUniverse; initialReadiness: ApprovedReadiness | null }) {
  const [state, formAction, pending] = useActionState(saveApprovedUniverse, {
    status: "idle", message: "", snapshot: null, submitted: null,
  } satisfies SaveState);
  const [draft, setDraft] = useState(initial.instruments.map(line).join("\n"));
  const [refreshed, setRefreshed] = useState<ApprovedReadiness | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [refreshing, startRefresh] = useTransition();
  const snapshot = state.snapshot ?? initial;
  const candidate = refreshed ?? initialReadiness;
  const readiness = candidate?.revision === snapshot.revision ? candidate : null;
  const stale = state.status === "stale";
  const editedAfterSave = state.status === "saved"
    && normalizedLineEndings(state.submitted ?? "") !== normalizedLineEndings(draft);
  return <>
    <p className={styles.status}>종목 등록 {snapshot.instruments.length ? "완료" : "대기"} · 성과 비교 준비 중 · 자동매매 미연결</p>
    {state.status !== "idle" && !editedAfterSave && <p className={state.status === "saved" ? styles.success : styles.error} role={state.status === "saved" ? "status" : "alert"}>{state.message} {stale && <button type="button" onClick={() => window.location.reload()}>현재 목록 다시 불러오기</button>}</p>}
    {editedAfterSave && <p className={styles.status} role="status">목록을 편집 중입니다. 변경 내용을 저장하려면 다시 저장하세요.</p>}
    <section className={styles.panel}>
      <h2>등록 목록</h2>
      {snapshot.instruments.length === 0 ? <p>아직 등록한 종목이 없습니다. 승인된 기본 종목은 없습니다.</p> : <ul>{snapshot.instruments.map((item) => <li key={`${item.market}-${item.exchange}-${item.symbol}`}>{item.market} · {item.exchange} · {item.symbol}</li>)}</ul>}
      <p>마지막 저장: {snapshot.updated_at ? new Date(snapshot.updated_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) + " KST" : "아직 없음"}</p>
    </section>
    <section className={styles.panel} aria-labelledby="readiness-heading">
      <h2 id="readiness-heading">등록 종목의 자료 수집 현황</h2>
      <p>단순 보유와 비용 포함 후보를 비교하기 전에 필요한 입력을 살펴봅니다. 수집 기록과 검토 건수는 자료 적격 판정이 아닙니다.</p>
      <p>다음 행동: 아래 현황을 갱신해 부족한 자료를 확인하세요. 개발 담당자가 종목 신원, 가격·배당·환율의 시점과 비용을 검증한 뒤 비교 조건을 정합니다.</p>
      <button type="button" className={styles.refresh} disabled={refreshing} onClick={() => {
        startRefresh(async () => {
          const result = await refreshApprovedReadiness();
          setRefreshed(result);
          setRefreshFailed(!result || result.revision !== snapshot.revision);
        });
      }}>{refreshing ? "갱신 중…" : "자료 현황 새로고침"}</button>
      {refreshFailed && <p className={styles.error} role="alert">현재 목록과 일치하는 자료 현황을 읽지 못했습니다. 다시 새로고침하세요.</p>}
      {!readiness && <p className={styles.status}>현재 목록의 자료 현황을 아직 확인하지 못했습니다. 새로고침해 확인하세요.</p>}
      {readiness && <>
        <p className={styles.status}>등록 목록 버전 {readiness.revision} · 확인 시각 {new Date(readiness.generated_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 성과 비교 미수행</p>
        <p>가격은 수집 메타데이터만 표시합니다. 시장·거래소와 같은 종목인지 확인되지 않았으므로 비교 입력으로 승인되지 않았습니다.</p>
        {readiness.instruments.length === 0 ? <p>등록 종목이 없어 종목별 현황이 없습니다.</p> : <div className={styles.readinessList}>{readiness.instruments.map(({ instrument, price, dividend }) => <article key={`${instrument.market}-${instrument.exchange}-${instrument.symbol}`} className={styles.readinessItem}>
          <h3>{instrument.market} · {instrument.exchange} · {instrument.symbol}</h3>
          <p><strong>가격:</strong> {priceLabel[price.status]}. {price.requested_start && price.requested_end ? `요청 ${price.requested_start}~${price.requested_end}, 실제 ${price.actual_start ?? "미확인"}~${price.actual_end ?? "미확인"}, 기존 자료의 평가 시작 ${price.evaluation_start ?? "미확인"}, 준비용 가격 ${price.warmup_bars ?? "미확인"}일, 요청 기간 안 가격 ${price.evaluation_bars ?? "미확인"}일.` : "기간·가격 일수 미확인."} 아직 성과 비교 전입니다.</p>
          {price.history_warning && <p className={styles.warning}>요청 시작보다 실제 이력 또는 평가 시작이 늦습니다. 같은 기간 비교 전 추가 확인이 필요합니다.</p>}
          <p><strong>배당:</strong> {dividend.status === "available" ? `현재 수집 이벤트 ${dividend.observed_event_count}건, 현재 수집 자료 버전에 검토 기록이 있는 이벤트 ${dividend.reviewed_current_event_count}건.` : "조회 불가."} 검토 기록은 적격 배당이나 완전한 총수익률 증거가 아닙니다. 이벤트 0건도 무배당 확인을 뜻하지 않습니다.</p>
        </article>)}</div>}
        <p><strong>USD/KRW:</strong> {readiness.fx.status === "available" ? `관측 날짜 ${readiness.fx.observed_date_count}개 (${readiness.fx.first_observed_on ?? "미확인"}~${readiness.fx.last_observed_on ?? "미확인"}).` : "조회 불가."} 거래 시점 가용성, 수정 이력과 환전 비용은 아직 검증하지 않았습니다.</p>
      </>}
    </section>
    <form action={formAction} className={styles.form}>
      <h2>목록 편집</h2>
      <label htmlFor="instruments">한 줄에 한 종목</label>
      <p id="format-help">한국: <code>KR,005930</code> 또는 <code>KR,0173Y0</code> · 미국: <code>US,NAS,AAPL</code>, <code>US,NYS,IBM</code>, <code>US,AMS,SPY</code>. 거래소는 NAS·NYS·AMS 중 하나를 명시하세요.</p>
      <textarea id="instruments" name="instruments" aria-describedby="format-help" rows={8} value={draft} onChange={(event) => setDraft(event.target.value)} />
      <input type="hidden" name="revision" value={snapshot.revision} />
      <label className={styles.check}><input type="checkbox" name="confirm_clear" /> 목록을 모두 비울 때 확인</label>
      <button type="submit" disabled={pending || stale}>{pending ? "저장 중…" : "이 목록 저장"}</button>
      <p>저장 후 위 등록 목록에 종목이 표시되는지 확인하세요. 저장은 목록만 바꾸며 비교나 주문을 시작하지 않습니다.</p>
    </form>
  </>;
}
