import Link from "next/link";
import {
  amount,
  marketNames,
  portfolioSchema,
  tone,
  type Portfolio,
} from "@/lib/portfolio";
import { Refresh } from "./refresh";
export const dynamic = "force-dynamic";

async function getPortfolio(): Promise<Portfolio | null> {
  try {
    const response = await fetch("http://127.0.0.1:8000/api/portfolio", {
      cache: "no-store",
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) return null;
    return portfolioSchema.parse(await response.json());
  } catch {
    return null;
  }
}

export default async function Home() {
  const data = await getPortfolio();
  const failed = data?.markets.filter((m) => m.status === "error") ?? [];
  const holdings = data?.markets.flatMap((m) => m.holdings) ?? [];
  const updated = data
    ? new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "Asia/Seoul",
      }).format(new Date(data.fetched_at))
    : null;
  return (
    <main>
      <header>
        <Link href="/" className="brand">
          <span className="mark">J</span> jusik
          <span className="brand-sub">나의 투자 현황</span>
        </Link>
        <span className="badge">실계좌 · 조회 전용</span>
      </header>
      <section className="intro">
        <div>
          <p className="eyebrow">MY PORTFOLIO</p>
          <h1>내 주식, 한눈에.</h1>
          <p className="muted">
            국내부터 해외까지, 보유 자산을 함께 확인하세요.
          </p>
        </div>
        <Refresh />
      </section>
      <div className="meta">
        <span>{updated ? `마지막 조회 ${updated} KST` : "잔고 연결 대기"}</span>
        <span>수동 갱신 · 30초 캐시</span>
      </div>
      {!data ? (
        <section role="alert" className="notice">
          <h2>잔고를 불러오지 못했습니다</h2>
          <p>백엔드 실행 상태와 KIS 인증 설정을 확인한 뒤 새로고침하세요.</p>
        </section>
      ) : (
        <>
          {failed.length > 0 && (
            <section role="alert" className="notice">
              <h2>일부 시장 조회 실패 · 합계는 조회 성공분만 포함</h2>
              {failed.map((m) => (
                <p key={m.market}>
                  {marketNames[m.market] ?? m.market}: {m.error}
                </p>
              ))}
            </section>
          )}
          <section className="cards" aria-label="통화별 보유 주식 평가">
            {data.totals.map((total) => (
              <article className="card" key={total.currency}>
                <div className="card-label">
                  <span>주식 평가금액</span>
                  <span className="currency">{total.currency}</span>
                </div>
                <p className="total">
                  {amount(total.value, total.currency === "KRW" ? 0 : 2)}
                  <small>{total.currency}</small>
                </p>
                <div className="card-bottom">
                  <span>평가손익</span>
                  <strong className={tone(total.profit)}>
                    {amount(total.profit)}{" "}
                    <span>
                      (
                      {total.return_pct === null
                        ? "—"
                        : `${amount(total.return_pct)}%`}
                      )
                    </span>
                  </strong>
                </div>
                <p className="cost">
                  매입금액 {amount(total.cost)} {total.currency}
                </p>
              </article>
            ))}
          </section>
          <section className="positions">
            <div className="section-title">
              <h2>
                보유 종목 <span>{holdings.length}</span>
              </h2>
              <span className="muted">거래 통화 기준</span>
            </div>
            <div className="table-wrap">
              <table>
                <caption className="sr-only">
                  국내 및 해외 보유 주식 잔고
                </caption>
                <thead>
                  <tr>
                    <th>종목 / 시장</th>
                    <th>수량</th>
                    <th>평균매입가</th>
                    <th>현재가</th>
                    <th>평가금액</th>
                    <th>평가손익</th>
                    <th>수익률</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={`${h.market}:${h.symbol}`}>
                      <td>
                        <strong>{h.name}</strong>
                        <small>
                          {h.symbol} · {marketNames[h.market] ?? h.market} ·{" "}
                          {h.currency}
                        </small>
                      </td>
                      <td>{amount(h.quantity, 8)}</td>
                      <td>{amount(h.average_price, 4)}</td>
                      <td>{amount(h.current_price, 4)}</td>
                      <td>{amount(h.value)}</td>
                      <td className={tone(h.profit)}>{amount(h.profit)}</td>
                      <td className={h.return_pct ? tone(h.return_pct) : ""}>
                        {h.return_pct === null
                          ? "—"
                          : `${amount(h.return_pct)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holdings.length === 0 && (
              <p className="empty">
                {failed.length
                  ? "조회에 성공한 시장에 보유 종목이 없습니다. 실패한 시장은 다시 조회하세요."
                  : "보유 중인 주식이 없습니다."}
              </p>
            )}
          </section>
          <div className="markets" aria-label="시장별 조회 상태">
            {data.markets.map((m) => (
              <span
                key={m.market}
                className={m.status === "error" ? "market-error" : ""}
              >
                {m.status === "ok" ? "✓" : "!"}{" "}
                {marketNames[m.market] ?? m.market}
              </span>
            ))}
          </div>
        </>
      )}
      <footer>
        한국투자증권 잔고 조회 기준 · 실시간 시세 스트리밍 아님
        <br />
        시장 휴장·시세 지연이 반영될 수 있습니다. 예수금·실현손익은 제외하며,
        통화 간 환산 없이 표시합니다.
      </footer>
    </main>
  );
}
