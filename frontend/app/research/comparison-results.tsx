import { researchAmount } from "@/lib/research";
import { comparisonBars } from "@/lib/research-chart";
import { compareDecimal, type Comparison, type Study } from "@/lib/research-progress";
import { getStudyNarrative, researchSettingLabels } from "@/lib/research-narrative";
import styles from "./comparison-results.module.css";

const metrics = [
  { key: "net_return_pct", title: "기간 전체 수익", meaning: "처음 가진 돈보다 얼마나 늘었는지", unit: "%", higher: "수익률 높아짐", lower: "수익률 낮아짐" },
  { key: "max_drawdown_pct", title: "도중 가장 큰 하락", meaning: "그때까지의 최고 금액에서 떨어진 최대 폭", unit: "%", higher: "하락 폭 커짐", lower: "하락 폭 작아짐" },
  { key: "total_cost_krw", title: "사고파는 데 든 비용", meaning: "거래·환전에 쓴 돈 · 적을수록 부담이 작음", unit: "원", higher: "비용 늘어남", lower: "비용 줄어듦" },
  { key: "cash_pct", title: "현금으로 남긴 몫", meaning: "전체 돈 중 주식에 넣지 않고 남겨 둔 비율", unit: "%", higher: "현금 늘어남", lower: "현금 줄어듦" },
] as const;

function changeLabel(comparison: Comparison, metric: (typeof metrics)[number]): string {
  const direction = compareDecimal(comparison.candidate[metric.key], comparison.baseline[metric.key]);
  return direction === 1 ? metric.higher : direction === -1 ? metric.lower : direction === 0 ? "같음" : "확인 불가";
}

export function ComparisonTakeaway({ study, comparison }: { study: Study; comparison: Comparison }) {
  if (!getStudyNarrative(study)) return <p className={styles.caution}>이 자료에 맞는 설명을 확인하지 못했습니다. 원문과 수치를 먼저 확인하세요.</p>;
  return <div className={styles.takeaway} aria-label="먼저 읽는 비교 결론">
    <p><strong>이 기간의 결론</strong> · 비교 시험에 비해 바꾼 시험은</p>
    <ul>{metrics.map((metric) => <li key={metric.key}>{changeLabel(comparison, metric)}</li>)}</ul>
    <small>{comparison.period_start}–{comparison.period_end} 과거 계산입니다. 실제 투자에 쓸 방식으로 결정한 것은 아닙니다.</small>
  </div>;
}

export function ComparisonResults({ comparison }: { study: Study; comparison: Comparison }) {
  return <section className={styles.results} aria-label="두 시험에서 관측한 결과">
    <h2>얻은 것과 감수한 것을 함께 보세요</h2>
    <p className={styles.period}>{comparison.period_start}–{comparison.period_end} · <strong>이 기간 전체의 과거 계산 결과</strong> · 매년의 수익률이 아닙니다.</p>
    <p className={styles.legend}><span><i className={styles.baselineKey} aria-hidden="true" />비교 시험</span><span><i className={styles.candidateKey} aria-hidden="true" />바꾼 시험</span><small>색은 시험을 구분합니다.</small></p>
    <div className={styles.charts}>{metrics.map((metric) => {
      const layout = comparisonBars(comparison.baseline[metric.key], comparison.candidate[metric.key]);
      return <figure key={metric.key} className={styles.chart} aria-label={`${metric.title} 비교`}>
        <figcaption><strong>{metric.title}</strong><span>{changeLabel(comparison, metric)}</span></figcaption>
        <p>{metric.meaning}</p>
        {(["baseline", "candidate"] as const).map((setting, index) => {
          const bar = layout.bars[index];
          return <div className={styles.measurement} key={setting}>
            <div className={styles.value}><span>{setting === "baseline" ? "비교 시험" : "바꾼 시험"}</span><strong>{bar ? `${researchAmount(comparison[setting][metric.key], metric.unit === "원" ? 0 : 2)}${metric.unit}` : "확인 불가"}</strong></div>
            <div className={styles.track} aria-hidden="true"><i className={styles.zero} style={{ left: `${layout.zero}%` }} />{bar && <span className={setting === "baseline" ? styles.baselineBar : styles.candidateBar} style={{ left: `${bar.left}%`, width: `${bar.width}%` }} />}</div>
          </div>;
        })}
        <div className={styles.axis} aria-hidden="true"><span style={{ left: `${layout.zero}%`, transform: layout.zero === 100 ? "translateX(-100%)" : layout.zero === 0 ? undefined : "translateX(-50%)" }}>0{metric.unit}</span></div>
      </figure>;
    })}</div>
    <p className={styles.precision}>항목마다 눈금이 다릅니다. 같은 항목의 두 막대만 비교하세요. 현금은 {comparison.cash_statistic === "mean" ? "일별 비율의 평균" : "일별 비율의 가운데 값(중앙값)"}, 하락은 {comparison.drawdown_basis === "close_nav" ? "하루 마감 가격으로 계산" : "연구의 모든 관측 시점으로 계산"}했습니다.</p>
    <details className={styles.details}><summary>숫자 읽는 예시와 계산 기준</summary>
      <p>처음 100만원이 마지막에 110만원이면 기간 전체 수익률은 +10%입니다. 도중에 120만원까지 올랐다가 108만원이 되면 그 구간의 하락은 10%입니다. 설명용 숫자이며 위 시험의 실제 금액은 아닙니다.</p>
      <p>현금 비율은 UTC 하루 마지막의 현금과 주식 가치를 합한 금액을 기준으로 합니다. {comparison.cash_statistic === "mean" ? "매일의 비율을 더해 날짜 수로 나눈 평균입니다." : "매일의 비율을 작은 순서로 놓았을 때 가운데 값입니다."} {comparison.drawdown_basis === "close_nav" ? "하락은 장 마감 가격으로 본 결과이며 장중 하락 전체를 뜻하지 않습니다." : "하락은 연구에서 관측한 모든 평가 시점의 금액을 사용합니다."}</p>
      <p>막대 길이는 비교를 위한 근사 표시입니다. 수치는 원래 자료에서 표시하며, 소수점 셋째 자리 이하를 버립니다. 원문 보고서의 반올림으로 43.18%가 여기서는 43.17%처럼 보일 수 있습니다.</p>
    </details>
    <details className={styles.details}><summary>거래 규모와 비용 가정 보기</summary>
      <p>거래·환전 비용을 기본 가정의 {comparison.cost_multiplier}배로 계산했습니다. 거래한 날이 줄어도 한 번에 사고파는 금액이 커지면 비용은 늘 수 있습니다.</p>
      <p className={styles.precision}>표가 잘리면 좌우로 밀어 읽으세요. 키보드는 표에 초점을 두고 좌우 방향키를 사용하세요.</p>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="거래 부담 비교 표"><table><thead><tr><th scope="col">확인할 내용</th><th scope="col">{researchSettingLabels.baseline}</th><th scope="col">{researchSettingLabels.candidate}</th></tr></thead><tbody>
        <tr><th scope="row">거래·환전에 든 비용 합계</th><td>{researchAmount(comparison.baseline.total_cost_krw, 0)}원</td><td>{researchAmount(comparison.candidate.total_cost_krw, 0)}원</td></tr>
        <tr><th scope="row">거래가 있었던 날 수</th><td>{comparison.baseline.trade_days}일</td><td>{comparison.candidate.trade_days}일</td></tr>
        <tr><th scope="row">연환산 회전율</th><td>{researchAmount(comparison.baseline.annual_turnover_pct, 2)}%</td><td>{researchAmount(comparison.candidate.annual_turnover_pct, 2)}%</td></tr>
      </tbody></table></div>
      <p>거래한 날 수는 주문 횟수와 다릅니다. 회전율은 자산 규모에 비해 사고판 규모를 1년 기준으로 환산한 값입니다. 수익률이 아니며 높을수록 거래 부담이 큽니다.</p>
    </details>
  </section>;
}
