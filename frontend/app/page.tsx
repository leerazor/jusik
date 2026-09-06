import Link from "next/link";
import {
  amount,
  marketNames,
  portfolioSchema,
  tone,
  type Account,
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

function accountStatus(account: Account): string {
  if (account.status === "ok") return "조회 완료";
  if (account.status === "partial") return "일부 조회";
  return "조회 실패";
}

function won(value: string | null): string {
  return value === null ? "조회 불가" : `${amount(value, 0)}원`;
}

export default async function Home() {
  const data = await getPortfolio();
  const failedAccounts =
    data?.accounts.filter((account) => account.status !== "ok") ?? [];
  const holdings =
    data?.accounts.flatMap((account) =>
      account.markets.flatMap((market) =>
        market.holdings.map((holding) => ({
          accountId: account.id,
          accountLabel: account.label,
          holding,
        })),
      ),
    ) ?? [];
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
          <p className="eyebrow">MY KIS ACCOUNTS</p>
          <h1>등록한 한투 계좌, 한눈에.</h1>
          <p className="muted">
            KIS Open API에 등록한 계좌의 국내·해외 주식과 원화 자산 요약입니다.
          </p>
        </div>
        <Refresh />
      </section>
      <div className="meta">
        <span>{updated ? `마지막 조회 ${updated} KST` : "계좌 연결 대기"}</span>
        <span>수동 갱신 · 30초 캐시</span>
      </div>
      {!data ? (
        <section role="alert" className="notice">
          <h2>계좌 정보를 불러오지 못했습니다</h2>
          <p>백엔드 실행 상태와 KIS 계좌 설정을 확인한 뒤 새로고침하세요.</p>
        </section>
      ) : (
        <>
          <section className="overview" aria-label="등록 계좌 통합 요약">
            <article className="hero-card">
              <span>조회 성공분 순자산</span>
              <strong>{won(data.aggregate.net_asset)}</strong>
              <small>
                {data.aggregate.completeness === "complete"
                  ? "등록 계좌 전체 반영"
                  : data.aggregate.completeness === "partial"
                    ? "일부 계좌만 반영한 합계"
                    : "확인 가능한 순자산 없음"}
              </small>
            </article>
            <article className="metric-card">
              <span>등록한 한투 계좌</span>
              <strong>{data.aggregate.registered_accounts}개</strong>
              <small>
                순자산 확인 {data.aggregate.included_accounts}개
              </small>
            </article>
            <article className="metric-card">
              <span>국내·해외 주식 종목</span>
              <strong>{holdings.length}개</strong>
              <small>계좌별 보유 건수 기준</small>
            </article>
          </section>

          {failedAccounts.length > 0 && (
            <section role="alert" className="notice">
              <h2>일부 조회 실패 · 합계는 조회 성공분만 포함</h2>
              {failedAccounts.map((account) => (
                <p key={account.id}>
                  {account.label}: {account.errors[0] ?? "계좌 조회 실패"}
                </p>
              ))}
            </section>
          )}

          <section className="account-section" aria-labelledby="account-title">
            <div className="section-title simple">
              <h2 id="account-title">계좌별 자산</h2>
              <span className="muted">원화 자산 요약</span>
            </div>
            <div className="account-grid">
              {data.accounts.map((account) => {
                const summary = account.asset_summary.summary;
                return (
                  <article className="account-card" key={account.id}>
                    <div className="account-heading">
                      <div>
                        <strong>{account.label}</strong>
                        <small>계좌번호 숨김</small>
                      </div>
                      <span className={`status status-${account.status}`}>
                        {accountStatus(account)}
                      </span>
                    </div>
                    <dl>
                      <div className="account-primary">
                        <dt>순자산</dt>
                        <dd>{won(summary?.net_asset ?? null)}</dd>
                      </div>
                      <div>
                        <dt>평가금액</dt>
                        <dd>{won(summary?.total_evaluation ?? null)}</dd>
                      </div>
                      <div>
                        <dt>예수금</dt>
                        <dd>{won(summary?.cash ?? null)}</dd>
                      </div>
                      <div>
                        <dt>평가손익</dt>
                        <dd className={tone(summary?.profit_loss ?? "0")}>
                          {won(summary?.profit_loss ?? null)}
                        </dd>
                      </div>
                      <div>
                        <dt>해외주식 평가</dt>
                        <dd>{won(summary?.overseas_evaluation ?? null)}</dd>
                      </div>
                    </dl>
                    <div className="markets" aria-label="시장별 조회 상태">
                      {account.markets.map((market) => (
                        <span
                          key={market.market}
                          className={market.status === "error" ? "market-error" : ""}
                          title={market.error ?? undefined}
                        >
                          {market.status === "ok" ? "✓" : "!"}{" "}
                          {marketNames[market.market] ?? market.market}
                        </span>
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section aria-labelledby="stock-summary-title">
            <div className="section-title simple">
              <h2 id="stock-summary-title">국내·해외 주식 평가</h2>
              <span className="muted">조회 성공분 합계 · 거래 통화 기준</span>
            </div>
            <div className="cards">
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
              {data.totals.length === 0 && (
                <p className="empty-card">조회된 보유 주식이 없습니다.</p>
              )}
            </div>
          </section>

          <section className="positions">
            <div className="section-title">
              <h2>
                보유 종목 <span>{holdings.length}</span>
              </h2>
              <span className="muted">계좌별 보유 건수</span>
            </div>
            <div className="table-wrap">
              <table>
                <caption className="sr-only">
                  등록한 한투 계좌의 국내 및 해외 보유 주식 잔고
                </caption>
                <thead>
                  <tr>
                    <th>계좌</th>
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
                  {holdings.map(({ accountId, accountLabel, holding }) => (
                    <tr key={`${accountId}:${holding.market}:${holding.symbol}`}>
                      <td className="account-cell">{accountLabel}</td>
                      <td>
                        <strong>{holding.name}</strong>
                        <small>
                          {holding.symbol} ·{" "}
                          {marketNames[holding.market] ?? holding.market} ·{" "}
                          {holding.currency}
                        </small>
                      </td>
                      <td>{amount(holding.quantity, 8)}</td>
                      <td>{amount(holding.average_price, 4)}</td>
                      <td>{amount(holding.current_price, 4)}</td>
                      <td>{amount(holding.value)}</td>
                      <td className={tone(holding.profit)}>
                        {amount(holding.profit)}
                      </td>
                      <td
                        className={
                          holding.return_pct ? tone(holding.return_pct) : ""
                        }
                      >
                        {holding.return_pct === null
                          ? "—"
                          : `${amount(holding.return_pct)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holdings.length === 0 && (
              <p className="empty">
                {failedAccounts.length
                  ? "조회에 성공한 계좌에 보유 주식이 없습니다. 실패한 계좌는 다시 조회하세요."
                  : "보유 중인 국내·해외 주식이 없습니다."}
              </p>
            )}
          </section>
        </>
      )}
      <footer>
        KIS Open API에 등록한 한국투자증권 계좌 조회 기준 · 실시간 시세 스트리밍 아님
        <br />
        순자산은 투자계좌자산현황의 원화 값을 계좌별로 한 번만 합산합니다. 주식
        평가액을 다시 더하지 않습니다. 통화별 주식 합계는 환산 없이 표시합니다.
      </footer>
    </main>
  );
}
