"use client";

import { useActionState, useState } from "react";
import { saveApprovedUniverse, type SaveState } from "./actions";
import type { ApprovedInstrument, ApprovedUniverse } from "./contract";
import styles from "./page.module.css";

function line(item: ApprovedInstrument): string {
  return item.market === "KR" ? `KR,${item.symbol}` : `US,${item.exchange},${item.symbol}`;
}

function normalizedLineEndings(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}

export function ApprovedUniverseEditor({ initial }: { initial: ApprovedUniverse }) {
  const [state, formAction, pending] = useActionState(saveApprovedUniverse, {
    status: "idle", message: "", snapshot: null, submitted: null,
  } satisfies SaveState);
  const [draft, setDraft] = useState(initial.instruments.map(line).join("\n"));
  const snapshot = state.snapshot ?? initial;
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
