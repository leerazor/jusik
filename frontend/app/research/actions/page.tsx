import Link from "next/link";
import {
  getActionCollectionStatus,
  getActionEvents,
  getActionReviews,
  getActionRevisions,
} from "@/lib/research";

export const dynamic = "force-dynamic";

function kst(value: string | null): string {
  return value
    ? `${new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`
    : "-";
}

const sourceState: Record<string, string> = {
  never: "수집 전", pending: "수집 중", success: "최근 성공",
  error: "최근 실패", interrupted: "중단 후 재시도 대기",
};
const collectorState: Record<string, string> = {
  idle: "대기", running: "수집 중", locked: "다른 수집 실행 중", error: "오류",
};
const reviewField: Record<string, string> = {
  split_ratio: "분할 비율", adjusted_trading_date: "조정 거래일",
  amount: "금액", currency: "통화", ex_dividend_date: "배당락일",
  comparable_share_basis: "비교 가능한 주식 기준",
};
function reviewedValue(value: string | null): string {
  return value ?? "확인 안 됨";
}

export default async function ResearchActionsPage({
  searchParams,
}: {
  searchParams: Promise<{
    eventsCursor?: string;
    revisionsCursor?: string;
    reviewsCursor?: string;
    reviewEvent?: string;
  }>;
}) {
  const query = await searchParams;
  const [statusResult, eventsResult, revisionsResult, reviewsResult] = await Promise.allSettled([
    getActionCollectionStatus(),
    getActionEvents(query.eventsCursor),
    getActionRevisions(query.revisionsCursor),
    getActionReviews(query.reviewsCursor, query.reviewEvent),
  ]);
  const status = statusResult.status === "fulfilled" ? statusResult.value : null;
  const events = eventsResult.status === "fulfilled" ? eventsResult.value : null;
  const revisions = revisionsResult.status === "fulfilled" ? revisionsResult.value : null;
  const reviews = reviewsResult.status === "fulfilled" ? reviewsResult.value : null;

  return (
    <main>
      <header className="research-result-header">
        <Link href="/research/forward" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">기업행동 관측</span></Link>
        <div className="action-row"><Link className="secondary-button" href="/research/forward">전진 PAPER</Link></div>
      </header>
      <section className="intro research-intro">
        <div><p className="eyebrow">UNVERIFIED SOURCE OBSERVATION</p><h1>기업행동 원문 관측</h1><p className="muted">Yahoo Chart의 최근 3년 분할·배당 메타데이터를 16종목별로 보존합니다. 이 자료는 미검증 관측이며 PAPER 원장에 자동 반영되지 않습니다.</p></div>
        <span className="badge">읽기 전용 수집</span>
      </section>
      {!status ? (
        <section className="notice" role="alert"><h2>수집 상태를 읽을 수 없습니다</h2><p>기업행동 저장소 장애는 전진 PAPER 판단과 원장 실행을 중단시키지 않습니다.</p></section>
      ) : (
        <>
          <section className="portfolio-metrics">
            <article className="metric-card"><span>수집기</span><strong>{collectorState[status.collector_state]}</strong><small>{status.error_code ?? "오류 없음"}</small></article>
            <article className="metric-card"><span>최근 성공 출처</span><strong>{status.sources.filter((item) => item.state === "success").length}/16</strong><small>상태 생성 {kst(status.generated_at)}</small></article>
            <article className="metric-card"><span>지연 출처</span><strong>{status.sources.filter((item) => item.stale).length}</strong><small>성공 후 24시간 기준</small></article>
          </section>
          <section className="panel research-step">
            <div className="section-title simple"><h2>16종목 수집 상태</h2><span className="status">종목별 독립 수집</span></div>
            <div className="table-wrap"><table><thead><tr><th>종목</th><th>상태</th><th>최근 시도</th><th>최근 성공</th><th>다음 예정</th><th>조회 구간</th><th>관측 수</th><th>최근 원문</th></tr></thead><tbody>{status.sources.map((source) => <tr key={source.symbol}><td>{source.symbol}<br /><small>{source.yahoo_symbol}</small></td><td>{sourceState[source.state]}{source.stale ? " · 지연" : ""}<br /><small>{source.error_code ?? "-"}</small></td><td>{kst(source.last_attempt_at)}</td><td>{kst(source.last_success_at)}</td><td>{kst(source.next_due_at)}</td><td>{source.requested_start && source.requested_end ? `${source.requested_start} ~ ${source.requested_end}` : "-"}</td><td>{source.event_count}</td><td>{source.latest_attempt_raw_available && source.latest_attempt_id ? <a href={`/research/actions/download/${source.latest_attempt_id}`}>원문</a> : "보존 원문 없음"}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
      <section className="panel research-step">
        <div className="section-title simple"><h2>공식 근거 대조</h2><span className="status">공식 문서와 수집값 비교</span></div>
        {!reviews ? <p className="empty-inline">공식 근거 대조를 읽을 수 없습니다. 수집과 PAPER 원장은 계속 독립 동작합니다.</p> : <>
          <div className="portfolio-metrics">
            <article className="metric-card"><span>현재 revision</span><strong>{reviews.current_revision_count}</strong><small>수집 이벤트의 현재 값</small></article>
            <article className="metric-card"><span>공식 근거 검토 revision</span><strong>{reviews.reviewed_revision_count}</strong><small>과거 revision 검토 포함</small></article>
            <article className="metric-card"><span>현재 미검토</span><strong>{reviews.unreviewed_current_revision_count}</strong><small>검토가 없는 현재 revision</small></article>
          </div>
          {query.reviewEvent && <p className="basis">선택한 이벤트의 검토만 표시합니다. <Link href="/research/actions">전체 검토 보기</Link></p>}
          {reviews.items.length === 0 ? <p className="empty-inline">{query.reviewEvent ? "이 이벤트의 현재 또는 과거 revision에 등록된 공식 근거 검토가 없습니다." : "등록된 공식 근거 검토가 없습니다."}</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>대조 결과</th><th>revision</th><th>필드 대조</th><th>보충 날짜</th><th>공식 근거</th><th>실제 검토·가져오기</th></tr></thead><tbody>{reviews.items.map((review) => <tr key={review.id}><td>{review.symbol}<br /><small>{review.kind === "split" ? "분할" : "배당"}</small></td><td>{review.comparison_status === "matched" ? "대조 필드 일치" : review.comparison_status === "partial" ? "부분 확인" : "불일치"}<br /><small>{review.current_revision ? "현재 revision" : "과거 revision · 재검토 필요"}</small></td><td>검토 #{review.sequence}<br /><small title={review.revision_id}>{review.revision_id.slice(0, 12)}…</small></td><td>{review.compared_fields.map((field) => <span key={field.field}>{field.field === "comparable_share_basis" ? <><strong>{reviewField[field.field]}</strong>: 근거 검토 {field.evidence_value === "true" ? "비교 가능" : field.evidence_value === "false" ? "비교 불가" : "확인 안 됨"}</> : <><strong>{reviewField[field.field] ?? field.field}</strong>: {field.status === "matched" ? "일치" : field.status === "missing" ? "확인 안 됨" : "불일치"}<br /><small>수집 {reviewedValue(field.source_value)} / 공식 {reviewedValue(field.evidence_value)}</small></>}<br /></span>)}</td><td>기준일 {review.extracted_facts.record_date ?? "확인 안 됨"}<br />지급일 {review.extracted_facts.payment_date ?? "확인 안 됨"}<br />법적 효력일 {review.extracted_facts.legal_effective_date ?? "확인 안 됨"}</td><td><a href={review.evidence.source_url}>{review.evidence.publisher}</a><br /><small>{review.evidence.locator}</small><br /><a href={`/research/actions/evidence/${review.evidence.id}`}>보존 원문</a></td><td>검토 {kst(review.reviewed_at)}<br />가져오기 {kst(review.imported_at)}<br /><small>근거 확보 {kst(review.evidence.captured_at)}</small></td></tr>)}</tbody></table></div>}
          {reviews.next_cursor && <div className="action-row"><Link className="secondary-button" href={`/research/actions?reviewsCursor=${reviews.next_cursor}${query.reviewEvent ? `&reviewEvent=${query.reviewEvent}` : ""}`}>다음 검토</Link></div>}
        </>}
        <p className="basis">대조 결과는 수집 freshness와 별개입니다. 공식 근거 검토 확인이며 지급 권리·세금·원장 반영 적격성을 뜻하지 않습니다.</p>
      </section>
      <section className="panel research-step">
        <div className="section-title simple"><h2>미검증 이벤트</h2><span className="status">최근 50건</span></div>
        <p className="basis">관측 상태는 해당 이벤트 날짜를 포함한 마지막 성공 조회 응답을 기준으로 합니다. 조회 범위 밖이 된 이벤트의 이전 상태는 보존됩니다.</p>
        {!events ? <p className="empty-inline">이벤트 목록을 읽을 수 없습니다.</p> : events.items.length === 0 ? <p className="empty-inline">관측된 이벤트가 없습니다.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>종류</th><th>공급자 날짜</th><th>현재 값</th><th>관측 상태</th><th>최초 관측</th><th>최근 관측</th><th>근거 검토</th><th>원문</th></tr></thead><tbody>{events.items.map((event) => <tr key={event.id}><td>{event.symbol}</td><td>{event.kind === "split" ? "분할" : "배당"}</td><td>{event.vendor_date}</td><td>{event.kind === "split" ? `${event.latest_revision.payload.numerator}:${event.latest_revision.payload.denominator}` : `${event.latest_revision.payload.amount} ${event.latest_revision.payload.currency}`}</td><td>{event.observation_state === "observed" ? "해당 날짜의 마지막 성공 조회에서 관측" : "해당 날짜의 마지막 성공 조회에서 미관측"}</td><td>{kst(event.first_seen_at)}</td><td>{kst(event.last_seen_at)}</td><td><Link href={`/research/actions?reviewEvent=${event.id}`}>검토 보기</Link></td><td><a href={`/research/actions/download/${event.latest_revision.attempt_id}`}>원문</a></td></tr>)}</tbody></table></div>}
        {events?.next_cursor && <div className="action-row"><Link className="secondary-button" href={`/research/actions?eventsCursor=${events.next_cursor}${query.revisionsCursor ? `&revisionsCursor=${query.revisionsCursor}` : ""}`}>다음 이벤트</Link></div>}
      </section>
      <section className="panel research-step">
        <div className="section-title simple"><h2>값 변경 이력</h2><span className="status">연속 동일 값 제외</span></div>
        {!revisions ? <p className="empty-inline">변경 이력을 읽을 수 없습니다.</p> : revisions.items.length === 0 ? <p className="empty-inline">기록된 revision이 없습니다.</p> : <div className="table-wrap"><table><thead><tr><th>종목</th><th>종류</th><th>공급자 날짜</th><th>순서</th><th>값</th><th>처음 관측</th><th>원문</th></tr></thead><tbody>{revisions.items.map((revision) => <tr key={revision.id}><td>{revision.symbol}</td><td>{revision.kind === "split" ? "분할" : "배당"}</td><td>{revision.payload.vendor_date}<br /><small title={revision.provider_key}>key {revision.provider_key}</small></td><td>{revision.sequence}</td><td>{revision.kind === "split" ? `${revision.payload.numerator}:${revision.payload.denominator}` : `${revision.payload.amount} ${revision.payload.currency}`}</td><td>{kst(revision.first_seen_at)}</td><td><a href={`/research/actions/download/${revision.attempt_id}`}>원문</a></td></tr>)}</tbody></table></div>}
        {revisions?.next_cursor && <div className="action-row"><Link className="secondary-button" href={`/research/actions?revisionsCursor=${revisions.next_cursor}${query.eventsCursor ? `&eventsCursor=${query.eventsCursor}` : ""}`}>다음 변경 이력</Link></div>}
      </section>
      <section className="notice quality-warning"><h2>관측 자료의 한계</h2><ul><li>공급자 이벤트 날짜이며 지급일, 세금, 공식 발표 시각은 알 수 없습니다.</li><li>최근 응답에서 보이지 않아도 취소·삭제로 확정하지 않습니다.</li><li>공식 근거 대조도 검증 split manifest에 자동 등록하거나 PAPER 원장에 자동 반영하지 않습니다.</li><li>배당 현금·세금·지급 권리는 계산하지 않습니다.</li></ul></section>
    </main>
  );
}
