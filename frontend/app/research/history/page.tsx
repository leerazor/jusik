import Link from "next/link";
import { getResearchHistory } from "@/lib/research";

export const dynamic = "force-dynamic";

function kst(value: string): string {
  return `${new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}

type PageProps = { searchParams: Promise<{ cursor?: string }> };

export default async function ResearchHistoryPage({ searchParams }: PageProps) {
  const query = await searchParams;
  let history = null;
  try { history = await getResearchHistory(query.cursor); } catch { history = null; }
  const artifacts = new Map(history?.artifacts.map((item) => [item.artifact_id, item]));
  return (
    <main>
      <header className="research-result-header"><Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">연구 이력</span></Link><Link className="secondary-button" href="/research/forward">전진 관찰</Link></header>
      <section className="intro"><div><p className="eyebrow">VERIFIABLE RESEARCH HISTORY</p><h1>검증과 수정의 기록</h1><p className="muted">과거 결과, 실패, 정정, 검증을 덮어쓰지 않고 시간순으로 공개합니다. 시각을 확인할 수 없는 과거 항목은 추정하지 않습니다.</p></div></section>
      {!history ? <section className="notice" role="alert"><h2>이력을 읽을 수 없습니다</h2><p>연구 백엔드 상태를 확인하세요.</p></section> : history.items.length === 0 ? <section className="panel"><p className="empty-inline">공개 이력을 아직 가져오지 않았습니다.</p></section> : <section className="history-list">{history.items.map((entry) => <article className="panel history-entry" key={entry.id}><div className="section-title simple"><h2>{entry.title}</h2><span className="status">{entry.outcome}</span></div><p>{entry.summary}</p><p className="basis">{entry.occurred_at ? kst(entry.occurred_at) : "발생 시각 미상"} · 기록 {kst(entry.recorded_at)} · {entry.category}</p>{entry.checks.length > 0 && <ul>{entry.checks.map((check) => <li key={`${entry.id}-${check.evidence_id}`}>{check.name}: {check.result}</li>)}</ul>}<div className="artifact-links">{entry.artifacts.map((reference) => { const artifact = artifacts.get(reference.artifact_id); return artifact ? <a key={reference.artifact_id} href={`/research/history/download/${reference.artifact_id}`}>{artifact.title}</a> : null; })}</div></article>)}{history.next_cursor && <Link className="secondary-button" href={`/research/history?cursor=${encodeURIComponent(history.next_cursor)}`}>이전 이력 25개 더 보기</Link>}</section>}
    </main>
  );
}
