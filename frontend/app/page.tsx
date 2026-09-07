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
import { HoldingsTable } from "./holdings-table";

export const dynamic = "force-dynamic";

async function getPortfolio(): Promise<Portfolio | null> {
  try {
    const backendUrl = process.env.JUSIK_BACKEND_URL ?? "http://127.0.0.1:8000";
    const response = await fetch(`${backendUrl}/api/portfolio`, {
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

function kst(value: string | null): string {
  return value ? new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value)) : "기록 없음";
}

const newsCategory = {
  korea_rate: "한국 금리",
  us_rate: "미국 금리",
  geopolitics: "국제 정세",
  truth_social: "Truth Social 관련 보도",
  truth_social_post: "트럼프 계정 게시물 · 제3자 보관본",
} as const;

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
          <p className="eyebrow">MY INVESTMENT ACCOUNTS</p>
          <h1>등록한 증권 계좌, 한눈에.</h1>
          <p className="muted">
            한국투자증권과 키움증권 계좌의 국내·해외 주식 및 자산 요약입니다.
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
          <p>백엔드 실행 상태와 증권사 계좌 설정을 확인한 뒤 새로고침하세요.</p>
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
              <span>등록한 증권 계좌</span>
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
          {data.holding_conversion_completeness !== "complete" && (
            <section role="alert" className="notice">
              <h2>일부 해외 보유분의 원화 환율을 확인하지 못했습니다</h2>
              <p>원화 주식 합계는 표시하지 않습니다. 원통화 잔고는 보유 종목에서 확인할 수 있습니다.</p>
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
                const primaryAsset =
                  summary?.net_asset ?? summary?.estimated_deposit_assets ?? null;
                const primaryLabel = summary?.net_asset ? "순자산" : "국내 추정예탁자산";
                return (
                  <article className="account-card" key={account.id}>
                    <div className="account-heading">
                      <div>
                        <strong>{account.label}</strong>
                        <small>
                          {account.broker === "kis" ? "한국투자증권" : "키움증권"} ·
                          계좌번호 숨김
                        </small>
                      </div>
                      <span className={`status status-${account.status}`}>
                        {accountStatus(account)}
                      </span>
                    </div>
                    <dl>
                      <div className="account-primary">
                        <dt>{primaryLabel}</dt>
                        <dd>{won(primaryAsset)}</dd>
                      </div>
                      <div>
                        <dt>
                          {summary?.scope === "domestic" ? "국내 평가금액" : "평가금액"}
                        </dt>
                        <dd>{won(summary?.total_evaluation ?? null)}</dd>
                      </div>
                      <div>
                        <dt>예수금</dt>
                        <dd>{won(summary?.cash ?? null)}</dd>
                      </div>
                      <div>
                        <dt>
                          {summary?.scope === "domestic" ? "국내 평가손익" : "평가손익"}
                        </dt>
                        <dd className={tone(summary?.profit_loss ?? "0")}>
                          {won(summary?.profit_loss ?? null)}
                        </dd>
                      </div>
                      <div>
                        <dt>해외주식 원화 평가</dt>
                        <dd>{won(summary?.overseas_evaluation ?? null)}</dd>
                      </div>
                      <div>
                        <dt>부채</dt>
                        <dd>{won(summary?.debt ?? null)}</dd>
                      </div>
                    </dl>
                    {summary && <p className="basis">산정 기준: {summary.basis} · {summary.asset_source}</p>}
                    {summary && Object.keys(summary.exchange_rates).length > 0 && (
                      <p className="basis">
                        키움 계좌 기준환율: {Object.entries(summary.exchange_rates).map(([currency, rate]) => `1 ${currency} = ${amount(rate, 4)}원`).join(" · ")}
                      </p>
                    )}
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
              <span className="muted">환율 확인이 끝난 보유분 · 원화 기준</span>
            </div>
            <div className="cards">
              {data.totals.map((total) => (
                <article className="card" key={total.currency}>
                  <div className="card-label">
                    <span>주식 평가금액</span>
                    <span className="currency">KRW</span>
                  </div>
                  <p className="total">
                    {amount(total.value_krw ?? total.value, 0)}
                    <small>원</small>
                  </p>
                  <div className="card-bottom">
                    <span>평가손익</span>
                    <strong className={tone(total.profit_krw ?? total.profit)}>
                      {amount(total.profit_krw ?? total.profit, 0)}원{" "}
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
                    매입금액 {amount(total.cost_krw ?? total.cost, 0)}원
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
            <HoldingsTable rows={holdings} />
            {holdings.length === 0 && (
              <p className="empty">
                {failedAccounts.length
                  ? "조회에 성공한 계좌에 보유 주식이 없습니다. 실패한 계좌는 다시 조회하세요."
                  : "보유 중인 국내·해외 주식이 없습니다."}
              </p>
            )}
          </section>

          <section className="insight-grid" aria-label="신호와 시장 소식">
            <article className="panel">
              <div className="section-title simple">
                <h2>감지 알림</h2>
                <span className="muted">
                  {data.monitor.telegram_configured ? "Telegram 전송 설정됨" : "앱 안에서만 표시"}
                </span>
              </div>
              {data.alerts.length ? data.alerts.slice(0, 8).map((alert) => (
                <div className="alert-row" key={alert.id}>
                  <strong>{alert.title}</strong>
                  <p>{alert.message}</p>
                  <small>{kst(alert.created_at)} · {alert.delivery === "telegram_sent" ? "Telegram 전송 완료" : alert.delivery === "telegram_unknown" ? "Telegram 전송 결과 불명" : alert.delivery === "telegram_failed" ? "Telegram 전송 실패" : "앱 알림"}</small>
                </div>
              )) : <p className="empty-inline">새 매수·매도 검토 신호가 없습니다.</p>}
              <p className="basis">{data.monitor.interval_seconds / 60}분 간격 감지 · 마지막 성공 {kst(data.monitor.last_success_at)} · 다음 감지 {kst(data.monitor.next_check_at)} · 연속 실패 {data.monitor.consecutive_failures}회 · 같은 신호는 상태가 바뀔 때까지 중복 알림하지 않습니다.</p>
              {data.monitor.error && <p role="alert" className="loss">{data.monitor.error}</p>}
            </article>
            <article className="panel">
              <div className="section-title simple">
                <h2>금리와 외부 소식</h2>
                <span className="muted">30분 캐시</span>
              </div>
              <div className="rate-strip">
                <span>한국 기준금리 <strong>{data.intelligence.korea_base_rate ? `${amount(data.intelligence.korea_base_rate)}%` : "조회 불가"}</strong><small>{data.intelligence.korea_rate_as_of ?? "기준일 없음"}</small></span>
                <span>미국 목표금리 <strong>{data.intelligence.us_target_rate ?? "조회 불가"}</strong><small>{data.intelligence.us_rate_as_of ?? "기준일 없음"}</small></span>
              </div>
              {data.intelligence.news.map((item) => (
                <div className="news-row" key={item.id}>
                  {item.category === "truth_social_post" ? (
                    <strong>{item.title}</strong>
                  ) : (
                    <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
                  )}
                  <small>{newsCategory[item.category]} · {item.source} · {kst(item.published_at)}</small>
                  {item.excerpt && <p>{item.excerpt}</p>}
                  {item.category === "truth_social_post" && (
                    <small>
                      <a href={item.url} target="_blank" rel="noreferrer">제3자 보관본</a>
                      {item.original_url && (
                        <> · <a href={item.original_url} target="_blank" rel="noreferrer">Truth Social 원문</a></>
                      )}
                    </small>
                  )}
                  <p>{item.assessment}</p>
                </div>
              ))}
              {!data.intelligence.news.length && <p className="empty-inline">소식 수집 대기 중입니다. 다음 갱신 때 다시 확인합니다.</p>}
              <details className="source-status">
                <summary>수집 소스 상태</summary>
                {data.intelligence.sources.map((source) => (
                  <p key={source.id}>
                    <a href={source.source_url} target="_blank" rel="noreferrer">{source.label}</a>: {source.status === "ok" ? "정상" : source.error ?? "실패"} · 마지막 수집 {kst(source.fetched_at)}{source.stale ? " · 이전 수집값" : ""}
                  </p>
                ))}
              </details>
              <details className="source-status">
                <summary>적용 환율</summary>
                {data.exchange_rates.map((rate) => (
                  <p key={rate.currency}>
                    <a href={rate.source_url} target="_blank" rel="noreferrer">{rate.currency} · {rate.source}</a>: {rate.krw_per_unit ? `1 ${rate.currency} = ${amount(rate.krw_per_unit, 4)}원` : rate.error ?? "조회 실패"} · 기준일 {rate.as_of ?? "없음"} · 수집 {kst(rate.fetched_at)}{rate.stale ? " · 오래된 값" : ""}
                  </p>
                ))}
              </details>
            </article>
          </section>
        </>
      )}
      <footer>
        한국투자증권 KIS 및 키움 REST API 계좌 조회 기준 · 실시간 시세 스트리밍 아님
        <br />
        해외자산은 확인된 일별 환율로 원화 환산합니다. 환율 또는 자산 구성요소가
        없으면 해당 값과 합계를 조회 불가로 표시합니다. 규칙 평가는 투자 자문이 아닌
        점검 신호이며, 주문 기능은 없습니다.
      </footer>
    </main>
  );
}
