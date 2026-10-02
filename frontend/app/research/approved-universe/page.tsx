import type { Metadata } from "next";
import Link from "next/link";
import { researchBackendUrl } from "@/lib/research";
import { saveApprovedUniverse } from "./actions";
import { approvedUniverseSchema, type ApprovedInstrument } from "./contract";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "비교할 종목 등록 · Jusik" };
export const dynamic = "force-dynamic";

type Search = { state?: string; revision?: string };

function line(item: ApprovedInstrument): string {
  return item.market === "KR" ? `KR,${item.symbol}` : `US,${item.exchange},${item.symbol}`;
}

const messages: Record<string, string> = {
  invalid: "형식을 확인하세요. 한국은 KR,종목코드 6자리, 미국은 US,거래소,티커 형식입니다. 중복 종목도 등록할 수 없습니다.",
  "confirm-clear": "목록을 비우려면 확인란을 선택한 뒤 다시 저장하세요.",
  stale: "다른 저장으로 목록이 바뀌었습니다. 현재 목록을 확인한 뒤 다시 편집하세요.",
  error: "저장 요청을 확인할 수 없습니다. 목록을 새로 확인하고 다시 시도하세요.",
};

export default async function ApprovedUniversePage({ searchParams }: { searchParams: Promise<Search> }) {
  const query = await searchParams;
  let snapshot: ReturnType<typeof approvedUniverseSchema.parse> | null = null;
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/approved-universe`, {
      cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (response.ok) snapshot = approvedUniverseSchema.parse(await response.json());
  } catch { /* Read failure is shown below; never imply an empty approved list. */ }
  const saved = query.state === "saved" && snapshot && query.revision === String(snapshot.revision);
  return <main className={styles.main}>
    <p className={styles.eyebrow}>새 연구의 첫 단계</p>
    <h1>단순 보유와 비교할 종목</h1>
    <p>직접 고른 한국·미국 종목을 등록하세요. 이 목록으로 단순 보유 기준과 거래가 적은 매수·보유·매도·현금 후보를 같은 조건에서 비교할 준비를 합니다.</p>
    <p className={styles.status}>종목 등록 {snapshot?.instruments.length ? "완료" : "대기"} · 성과 비교 준비 중 · 자동매매 미연결</p>
    {saved && snapshot && <p className={styles.success} role="status">저장 완료 · 현재 목록 {snapshot.revision}판</p>}
    {query.state && !saved && <p className={styles.error} role="alert">{messages[query.state] ?? "저장 상태를 확인할 수 없습니다. 현재 목록을 다시 확인하세요."}</p>}
    {!snapshot ? <p className={styles.error} role="alert">등록 목록을 읽지 못했습니다. 연결을 확인한 뒤 새로고침하세요. 저장은 사용할 수 없습니다.</p> : <>
      <section className={styles.panel}>
        <h2>등록 목록</h2>
        {snapshot.instruments.length === 0 ? <p>아직 등록한 종목이 없습니다. 승인된 기본 종목은 없습니다.</p> : <ul>{snapshot.instruments.map((item) => <li key={`${item.market}-${item.exchange}-${item.symbol}`}>{item.market} · {item.exchange} · {item.symbol}</li>)}</ul>}
        <p>마지막 저장: {snapshot.updated_at ? new Date(snapshot.updated_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) + " KST" : "아직 없음"}</p>
      </section>
      <form action={saveApprovedUniverse} className={styles.form}>
        <h2>목록 편집</h2>
        <label htmlFor="instruments">한 줄에 한 종목</label>
        <p id="format-help">한국: <code>KR,005930</code> 또는 <code>KR,0173Y0</code> · 미국: <code>US,NAS,AAPL</code>, <code>US,NYS,IBM</code>, <code>US,AMS,SPY</code>. 거래소는 NAS·NYS·AMS 중 하나를 명시하세요.</p>
        <textarea id="instruments" name="instruments" aria-describedby="format-help" rows={8} defaultValue={snapshot.instruments.map(line).join("\n")} />
        <input type="hidden" name="revision" value={snapshot.revision} />
        <label className={styles.check}><input type="checkbox" name="confirm_clear" /> 목록을 모두 비울 때 확인</label>
        <button type="submit">이 목록 저장</button>
      </form>
    </>}
    <p className={styles.next}>다음 단계: 등록 종목의 가격·배당·환율 자료를 검증한 뒤 같은 종목의 단순 보유 기준과 비용을 포함해 비교합니다. 등록만으로 자료 적격성이나 거래가 승인되지는 않습니다.</p>
    <Link href="/research">연구 첫 화면으로 돌아가기</Link>
  </main>;
}
