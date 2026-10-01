import {
  summarizePortfolioDecisionReasons,
  type PortfolioPolicyComparison,
} from "@/lib/portfolio-decision-reasons";

export const policyLabels = {
  corrected_control: "체결 수정 대조군",
  reentry_only: "재진입만",
  volatility_only: "변동성 배율만",
  combined: "재진입 + 변동성",
  low_turnover_combined: "저회전 결합",
} as const;

type DecisionReasonComparison = Pick<PortfolioPolicyComparison, "policy"> & {
  base: Pick<PortfolioPolicyComparison["base"], "policy_events">;
};

export function PolicyDecisionReasons({ comparisons }: { comparisons: readonly DecisionReasonComparison[] }) {
  const policies = comparisons.map((comparison) => ({
    policy: comparison.policy,
    summary: summarizePortfolioDecisionReasons(comparison.base.policy_events),
  }));
  return (
    <section aria-labelledby="decision-reasons-heading">
      <div className="section-title simple subsection-title"><h3 id="decision-reasons-heading">거래하지 않은 이유</h3><span className="muted">정책별 기본 비교 기록</span></div>
      <p className="basis">기록된 사건은 조정을 건너뛰거나 제약 처리를 보류한 경우입니다. 건수의 단위가 달라 합산하지 않으며, 거래 건수나 현금 보유 기간·금액, 거래가 없었던 유일한 원인을 뜻하지 않습니다.</p>
      {policies.length === 0 ? (
        <p className="basis">비교할 정책 기록이 없어 사유를 알 수 없습니다.</p>
      ) : (
        <>
          <div className="table-wrap"><table><thead><tr><th>정책</th><th>재배분 주기로 건너뜀<br />평가 회</th><th>작은 비중 차이로 건너뜀<br />종목 건</th><th>상한 초과 처리 보류<br />기록 건</th><th>기록 해석</th></tr></thead><tbody>
            {policies.map(({ policy, summary }) => <tr key={policy}><td>{policyLabels[policy]}</td><td>{summary.counts.frequency_skip}</td><td>{summary.counts.band_skip}</td><td>{summary.counts.cap_constraint_deferred}</td><td>{summary.events.length === 0 ? "기록된 사유 없음 · 원인 알 수 없음" : "아래 원문 확인"}</td></tr>)}
          </tbody></table></div>
          <p className="basis">상한 초과 처리 보류는 당시 조정 대상이 아닌 보유분이 보수적으로 계산한 한도를 넘었다는 기록입니다. 모든 매매가 중단됐다는 뜻은 아닙니다. 기록이 없어도 신호가 없었다고 단정할 수 없습니다.</p>
          {policies.map(({ policy, summary }) => <details className="technical-details" key={policy}>
            <summary>{policyLabels[policy]} · 사유 원문 {summary.events.length}건</summary>
            {summary.events.length === 0 ? <p>기록된 사유가 없어 원인은 알 수 없습니다.</p> : (
              <div className="table-wrap"><table><thead><tr><th>at (UTC)</th><th>kind</th><th>detail</th><th>value</th></tr></thead><tbody>
                {summary.events.map((event, index) => <tr key={index}><td>{event.at}</td><td>{event.kind}</td><td>{event.detail}</td><td>{event.value ?? "—"}</td></tr>)}
              </tbody></table></div>
            )}
          </details>)}
        </>
      )}
    </section>
  );
}
