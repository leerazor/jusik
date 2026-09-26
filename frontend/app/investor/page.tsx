import Link from "next/link";
import { getInvestorCandidates, getTheses, type Discovery, type Thesis } from "@/lib/investor";

export const dynamic = "force-dynamic";

function formattedShares(value: string | null): string {
  if (!value) return "확인 불가";
  const [integer, fraction] = value.split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction ? `${grouped}.${fraction}` : grouped;
}

function formattedRatio(value: string | null): string {
  if (!value) return "확인 불가";
  const [integer, fraction = ""] = value.split(".");
  return `${integer}.${(fraction + "00").slice(0, 2)}`;
}

function CandidateList({ candidates, title }: { candidates: Discovery["candidates"]; title: string }) {
  return <><h3>{title}</h3>{candidates.length === 0 ? <p className="muted">조건에 맞는 후보가 없습니다.</p> : <ul className="candidate-list">{candidates.map((candidate) => <li key={`${candidate.instrument.market}-${candidate.instrument.exchange}-${candidate.instrument.symbol}`}><Link href={`/investor/${candidate.instrument.market}/${candidate.instrument.symbol}?exchange=${candidate.instrument.exchange}`}><strong>{candidate.instrument.name}</strong><span>{candidate.instrument.symbol} · {candidate.instrument.exchange} · {candidate.instrument.instrument_type === "etf" ? "ETF" : "주식"}</span></Link><small>KIS 순위 거래량 {formattedShares(candidate.ranking_volume)}주</small>{candidate.relative_volume?.ratio !== null && candidate.relative_volume ? <><small>Yahoo 누적량 {formattedShares(candidate.relative_volume.numerator)}주 ÷ 직전 20거래일 하루 평균 {formattedShares(candidate.relative_volume.average20)}주 = {formattedRatio(candidate.relative_volume.ratio)}배</small><details><summary>상대거래량 기준 보기</summary><small>비교 기간 {candidate.relative_volume.sample_start ?? "확인 불가"} ~ {candidate.relative_volume.sample_end ?? "확인 불가"} · 기준 시각 {candidate.relative_volume.as_of ? new Date(candidate.relative_volume.as_of).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) : "확인 불가"} KST · 조회 {new Date(candidate.relative_volume.fetched_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST. KIS 순위 수량과 다른 자료이며 장중 동시간 평균이나 전망치가 아닙니다.</small></details></> : <small className="investor-error">상대거래량 확인 필요{candidate.relative_volume?.unavailable_reason ? ` · ${candidate.relative_volume.unavailable_reason}` : ""}</small>}</li>)}</ul>}</>;
}

function CandidateBlock({ result }: { result: Discovery | null }) {
  if (!result) return <section className="investor-panel" role="alert"><h2>후보 자료를 확인할 수 없습니다</h2><p>연결 실패와 후보 없음은 같은 의미가 아닙니다. 백엔드 상태를 확인하세요.</p></section>;
  return <section className="investor-panel"><div className="investor-panel-heading"><h2>{result.market === "KR" ? "한국 시장" : "미국 시장"} 후보</h2><span>주식 {result.candidates.length}건 · ETF {result.etf_candidates.length}건</span></div><p className="muted">{result.coverage} 확인 시각 {new Date(result.fetched_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST.</p><p className="muted">전체 {result.counts.source_rows}건 중 {result.counts.inspected}건을 분류했습니다. 순위 거래량은 KIS 누적 수량, 상대거래량은 Yahoo의 직전 완료 20거래일 평균과 비교합니다.</p>{result.errors.map((error) => <p className="investor-error" role="alert" key={error}>{error}</p>)}<CandidateList candidates={result.candidates} title="주식 후보" /><CandidateList candidates={result.etf_candidates} title="ETF 후보" />{result.counts.unknown > 0 && <p className="muted">타입을 확인하지 못한 {result.counts.unknown}건은 후보 목록에서 제외했습니다.</p>}{result.counts.unscanned > 0 && <p className="muted">조회 한도로 {result.counts.unscanned}건은 분류하지 않았습니다.</p>}</section>;
}

function ThesisList({ theses }: { theses: Thesis[] }) {
  return <section className="investor-panel" aria-labelledby="saved-theses"><div className="investor-panel-heading"><h2 id="saved-theses">저장한 투자 메모</h2><span>{theses.length}건</span></div>{theses.length === 0 ? <p className="muted">아직 저장한 연구 기록이 없습니다. 종목을 열어 근거와 무효화 조건을 직접 기록하세요.</p> : <ul className="thesis-list">{theses.map((thesis) => <li key={thesis.id}><Link href={`/investor/${thesis.instrument.market}/${thesis.instrument.symbol}?exchange=${thesis.instrument.exchange}`}><strong>{thesis.instrument.name}</strong><span>{thesis.state} · {thesis.entry_kind === "value" ? "가치 진입" : "초기 추세 진입"} · revision {thesis.revision}</span></Link><small>다음 검토 {thesis.next_review} · 상태 {thesis.health}</small></li>)}</ul>}</section>;
}

export default async function InvestorPage() {
  const [kr, us, theses] = await Promise.all([getInvestorCandidates("KR"), getInvestorCandidates("US"), getTheses()]);
  return <main className="investor-main"><header className="investor-header"><div><p className="eyebrow">선택 도구 · 개별 종목 탐색</p><h1>종목 직접 연구</h1><p className="lede">관심 있는 종목을 직접 찾아보고 투자 메모를 남기는 선택 도구입니다. 연구 결과를 읽기 위해 이 화면을 이용할 필요는 없습니다. 메모는 매수 추천이나 실제 체결 기록이 아닙니다.</p></div><div className="action-row"><Link className="secondary-button" href="/research">연구 한눈에 보기</Link><Link className="secondary-button" href="/">계좌 현황</Link></div></header><section className="investor-walkthrough" aria-labelledby="walkthrough-title"><h2 id="walkthrough-title">처음이라면 이렇게 읽으세요</h2><ol><li><strong>발견</strong><span>한국·미국 첫 순위 페이지와 직접 조회로 후보를 고릅니다.</span></li><li><strong>확인</strong><span>현재가·재무·추세의 source, 기준 시각, 누락 이유를 확인합니다.</span></li><li><strong>기록</strong><span>왜 보는지, 무엇이 무효화하는지, 다음 검토일을 직접 적습니다.</span></li></ol></section><section className="investor-panel" aria-labelledby="interpretation-title"><h2 id="interpretation-title">현재 가치와 역사적 관찰 구분</h2><p><strong>현재 가치 가정:</strong> 사용자가 입력한 정규화 EPS·목표 PER·안전마진과 현재 확인 자료로 계산합니다. 가치 분석은 역사적 연구의 진입 신호가 아닙니다. 오늘의 EPS·PER·가치평가를 과거 날짜의 근거로 소급하지 않으며, 역사적 가치 판단에는 그때 이용 가능했던 자료가 필요합니다.</p><p><strong>역사적 추세 관찰:</strong> 완료 일봉의 종가가 직전 완료 20세션 고점을 넘고 거래량이 직전 완료 20세션 평균 거래량을 넘었는지, 또는 SMA20 아래가 2회 연속인지 따로 관찰합니다. 이는 가치 가정과 다른 자료 흐름이며 자동 주문이나 체결을 뜻하지 않습니다.</p></section><section className="investor-panel"><h2>직접 조회</h2><form className="lookup-form" action="/investor/lookup"><label>시장<select name="market" defaultValue="KR"><option value="KR">한국</option><option value="US">미국</option></select></label><label>종목 코드<input name="symbol" required maxLength={16} pattern="[A-Za-z0-9.-]+" placeholder="005930 또는 AAPL" /></label><button type="submit">상세 확인</button></form><p className="muted">URL을 입력받거나 임의 주소를 가져오지 않습니다. 허용된 시장·코드만 조회합니다.</p></section><div className="investor-grid"><CandidateBlock result={kr} /><CandidateBlock result={us} /></div><ThesisList theses={theses} /><section className="investor-footnote"><strong>범위와 한계</strong><p>현재 자료의 분석이며 과거 시점의 정보 가용성이나 투자 성과를 주장하지 않습니다. 후보 순위는 전체 시장을 보장하지 않고, ETF·타입 미확인 종목에는 기업 EPS 가치평가를 적용하지 않습니다.</p></section></main>;
}
