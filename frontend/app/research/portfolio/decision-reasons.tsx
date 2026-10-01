import {
  summarizePortfolioDecisionReasons,
  type PortfolioDecisionEvent,
  type PortfolioPolicyComparison,
} from "@/lib/portfolio-decision-reasons";

export const policyLabels = {
  corrected_control: "체결 수정 대조군",
  reentry_only: "재진입만",
  volatility_only: "변동성 배율만",
  combined: "재진입 + 변동성",
  low_turnover_combined: "저회전 결합",
} as const;

const reasonLabels: Partial<Record<PortfolioDecisionEvent["kind"], string>> = {
  frequency_skip: "재배분 주기로 건너뜀",
  band_skip: "작은 비중 차이로 건너뜀",
  cap_constraint_deferred: "상한 초과 처리 보류",
};

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
      <p className="basis">연구 프로그램이 과거 자료에 정책별 규칙을 적용하며 남긴 기록입니다. 재배분 주기로 건너뜀은 재배분 여부를 평가할 때 예정된 주기가 아직 지나지 않아 조정을 건너뛴 횟수입니다. 작은 비중 차이로 건너뜀은 종목의 현재 비중과 목표 비중 차이가 설정 범위 안이라 조정을 건너뛴 기록입니다. 건수의 단위가 달라 합산하지 않으며, 거래 건수나 현금 보유 기간·금액, 거래가 없었던 유일한 원인을 뜻하지 않습니다.</p>
      {policies.length === 0 ? (
        <p className="basis">비교할 정책 기록이 없어 사유를 알 수 없습니다.</p>
      ) : (
        <>
          <p className="basis">표가 잘리면 좌우로 밀어 나머지 열을 확인하세요.</p>
          <div className="table-wrap decision-reason-summary"><table><thead><tr><th>정책</th><th>재배분 주기로 건너뜀<br />평가 회</th><th>작은 비중 차이로 건너뜀<br />종목 건</th><th>상한 초과 처리 보류<br />기록 건</th><th>기록 해석</th></tr></thead><tbody>
            {policies.map(({ policy, summary }) => <tr key={policy}><td>{policyLabels[policy]}</td><td>{summary.counts.frequency_skip}</td><td>{summary.counts.band_skip}</td><td>{summary.counts.cap_constraint_deferred}</td><td>{summary.events.length === 0 ? "기록된 사유 없음 · 원인 알 수 없음" : "아래 원문 확인"}</td></tr>)}
          </tbody></table></div>
          <p className="basis">상한 초과 처리 보류는 당시 조정 대상이 아닌 보유분이 보수적으로 계산한 한도를 넘었다는 기록입니다. 모든 매매가 중단됐다는 뜻은 아닙니다. 원문 설명의 주기 표현만으로 실제 적용 간격을 확정하지 않습니다. 기록이 없어도 신호가 없었다고 단정할 수 없습니다.</p>
          {policies.map(({ policy, summary }) => <details className="technical-details" key={policy}>
            <summary>{policyLabels[policy]} · 사유 원문 {summary.events.length}건</summary>
            {summary.events.length === 0 ? <p>기록된 사유가 없어 원인은 알 수 없습니다.</p> : (
              <><p className="basis">표가 잘리면 좌우로 밀어 나머지 열을 확인하세요.</p><div className="table-wrap decision-reason-evidence"><table><thead><tr><th>시각 (UTC)</th><th>사건 종류 (kind)</th><th>원문 설명 (detail)</th><th>원문 값 (value)</th></tr></thead><tbody>
                {summary.events.map((event, index) => <tr key={index}><td data-label="시각 (UTC)">{event.at}</td><td data-label="사건 종류">{reasonLabels[event.kind] ?? event.kind}<small>{event.kind}</small></td><td data-label="원문 설명">{event.detail}</td><td data-label="원문 값">{event.value ?? "—"}</td></tr>)}
              </tbody></table></div></>
            )}
          </details>)}
        </>
      )}
    </section>
  );
}
