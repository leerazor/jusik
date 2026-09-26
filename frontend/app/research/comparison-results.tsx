import { researchAmount } from "@/lib/research";
import { type Comparison, type Study } from "@/lib/research-progress";
import { describeComparisonOutcome, getStudyNarrative, researchSettingLabels } from "@/lib/research-narrative";
import styles from "./comparison-results.module.css";

export function ComparisonResults({ study, comparison }: { study: Study; comparison: Comparison }) {
  const narrative = getStudyNarrative(study);
  const rows = [
    { label: "마지막에 돈이 얼마나 늘었나요?", meaning: "처음 가진 돈과 마지막 금액을 비교한 기간 전체 수익률입니다. 예: 100만원이 110만원이면 +10%입니다.", key: "net_return_pct" },
    { label: "도중에 얼마나 크게 떨어졌나요?", meaning: `그때까지 가장 높았던 금액에서 떨어진 최대 폭입니다. 예: 120만원에서 108만원이 되면 10% 하락입니다. ${comparison.drawdown_basis === "close_nav" ? "하루 장이 끝난 가격으로 계산한 금액만 봅니다. 장중 하락 전체를 뜻하지 않습니다." : "연구에서 관측한 모든 평가 시점의 금액으로 계산했습니다."}`, key: "max_drawdown_pct" },
    { label: "얼마나 현금으로 남겨 두었나요?", meaning: `매일 현금과 주식의 가치를 합한 돈 중 현금으로 남은 몫입니다. ${comparison.cash_statistic === "mean" ? "매일의 현금 비율을 더해 날짜 수로 나눈 평균입니다." : "매일의 현금 비율을 작은 순서로 놓았을 때 가운데 값(중앙값)입니다."}`, key: "cash_pct" },
  ] as const;
  return <section className={styles.results} aria-label="두 시험에서 관측한 결과">
    <h2>그래서, 어떤 차이가 있었나요?</h2>
    <p className={styles.period}>{comparison.period_start}부터 {comparison.period_end}까지의 <strong>과거 계산 결과</strong>입니다. 수익률은 이 기간 전체의 변화이며, 매년 이만큼 번다는 뜻이 아닙니다.</p>
    <div className={styles.header}><span>읽을 숫자 3가지</span><strong>{researchSettingLabels.baseline}</strong><strong>{researchSettingLabels.candidate}</strong></div>
    <dl className={styles.rows}>{rows.map((row) => <div key={row.key} className={styles.row}>
      <dt>{row.label}<small>{row.meaning}</small></dt>
      <dd><span>{researchSettingLabels.baseline}</span>{researchAmount(comparison.baseline[row.key], 2)}%</dd>
      <dd><span>{researchSettingLabels.candidate}</span>{researchAmount(comparison.candidate[row.key], 2)}%</dd>
    </div>)}</dl>
    <div className={styles.interpretation}><strong>이 기간·조건에서 확인한 차이</strong><p>{narrative ? `바꾼 시험은 비교의 출발점인 시험보다 ${describeComparisonOutcome(comparison)}` : "이 자료에 맞는 연구 설명을 확인하지 못했습니다. 표시된 수치만으로 더 좋은 투자법을 정하지 마세요."}</p><p>더 높은 수익을 얻은 경우에도 중간 하락과 비용을 함께 보세요. 이 비교 하나로 실제 투자에 쓸 방식이 결정되지는 않습니다.</p></div>
    <details className={styles.details}><summary>사고파는 데 든 비용과 거래 규모 보기</summary>
      <p>거래 횟수가 줄어도 한 번에 사고파는 금액이 커지면 비용은 늘 수 있습니다. 이 비교는 거래·환전 비용을 기본 가정의 {comparison.cost_multiplier}배로 놓고 계산했습니다.</p>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="거래 부담 비교 표"><table><thead><tr><th>확인할 내용</th><th>{researchSettingLabels.baseline}</th><th>{researchSettingLabels.candidate}</th></tr></thead><tbody>
        <tr><th>거래·환전에 든 비용 합계</th><td>{researchAmount(comparison.baseline.total_cost_krw, 0)}원</td><td>{researchAmount(comparison.candidate.total_cost_krw, 0)}원</td></tr>
        <tr><th>거래가 있었던 날 수</th><td>{comparison.baseline.trade_days}일</td><td>{comparison.candidate.trade_days}일</td></tr>
        <tr><th>연환산 회전율</th><td>{researchAmount(comparison.baseline.annual_turnover_pct, 2)}%</td><td>{researchAmount(comparison.candidate.annual_turnover_pct, 2)}%</td></tr>
      </tbody></table></div>
      <p>거래가 있었던 날 수는 주문 횟수와 다릅니다. 회전율은 자산 규모에 비해 얼마나 많이 사고팔았는지를 1년 기준으로 환산한 수치입니다. 수익률이 아니며 높을수록 거래 부담이 큽니다.</p>
    </details>
    <p className={styles.precision}>숫자 표시: 이 화면은 소수점 셋째 자리 이하를 버려 두 자리까지 표시합니다. 보고서에서 반올림한 43.18%가 여기서는 43.17%처럼 보일 수 있습니다. 원문 수치는 보고서에 그대로 있습니다.</p>
  </section>;
}
