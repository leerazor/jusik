import { getComparisonSettings, getStudyNarrative, researchCadenceExplanation, researchSettingLabels } from "@/lib/research-narrative";
import type { Study } from "@/lib/research-progress";
import styles from "./comparison-settings.module.css";

export function ComparisonSettings({ study, comparisonId }: { study: Study; comparisonId: string }) {
  const settings = getComparisonSettings(study, comparisonId);
  const narrative = getStudyNarrative(study);
  return <section className={styles.settings} aria-label="비교한 연구 설정">
    <p className={styles.context}><strong>연구자가 만든 두 시험</strong> · 사용자의 투자 이력이 아닙니다.</p>
    {settings && narrative ? <>
      <table className={styles.comparisonTable}>
        <caption>무엇을 바꿨나요?</caption>
        <thead><tr><th scope="col">확인할 행동</th><th scope="col">비교 시험</th><th scope="col">바꾼 시험</th></tr></thead>
        <tbody>{settings.rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td>{row.baseline}</td><td>{row.candidate}</td></tr>)}</tbody>
      </table>
      <p className={styles.note}>{settings.multipleChanges ? "한도·투자금 조절·점검 간격 등을 함께 바꿨습니다. 주기 하나의 효과로 결론낼 수 없습니다. 2%p는 20%와 22%의 비율 차이를 뜻합니다." : "표에 없는 나머지 규칙은 같게 두고 비교했습니다."}</p>
      <details className={styles.details}>
        <summary>설정값의 뜻과 금액 예시</summary>
        <p className={styles.example}><strong>설명용 예시 · 실제 연구 결과와 다릅니다.</strong> {narrative.reading.example}</p>
        <div className={styles.columns}><div><h4>{researchSettingLabels.baseline}</h4><ul>{settings.baselineRules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div><div><h4>{researchSettingLabels.candidate}</h4><ul>{settings.candidateRules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div></div>
        <dl className={styles.glossary}>
          <div><dt>가격이 크게 흔들리면 투자금을 줄입니다 · 연 변동성 목표</dt><dd>최근 가격이 오르내린 정도를 계산해 투자 규모를 조절합니다. 목표값을 높이면 같은 흔들림에서 투자금을 덜 줄일 수 있습니다. 목표 10%·15%·30%는 약속된 수익률이나 최대 손실 한도가 아닙니다.</dd></div>
          <div><dt>목표와 차이가 작으면 거래를 건너뜁니다 · 보유 비중 밴드</dt><dd>비중은 전체 돈 중 한 종목에 들어간 몫입니다. 예를 들어 전체 100만원에서 목표 20만원, 현재 21만원이면 차이는 1%p입니다. 밴드 2%p보다 작으므로, 다른 투자 한도도 지키고 있다면 그대로 둘 수 있습니다. %p는 두 비율을 뺀 차이입니다.</dd></div>
          <div><dt>한 투자 구간에서 크게 떨어지면 매도를 결정합니다 · 에피소드 손실 제한</dt><dd>투자 시작부터 현금과 보유 주식의 가치를 합한 금액의 최고점을 추적합니다. 종가로 계산한 금액이 그 최고점보다 10% 이상 떨어지면 보유분을 팔도록 결정합니다. 모두 판 뒤 다시 투자할 때는 그때 금액으로 새 구간을 시작합니다. 실제 매도 가격과 재투자 후 손실 때문에 전체 기간의 손실이 10% 안에 멈춘다는 보장은 없습니다.</dd></div>
        </dl>
        {settings.cadenceChanged && <p className={styles.note}>{researchCadenceExplanation}</p>}
      </details>
    </> : <p className={styles.explanation}>이 자료에 맞는 규칙 설명을 확인할 수 없습니다. 구체적인 행동을 추측해서 설명하지 않으며, 확인된 수치와 원본 보고서를 보여줍니다.</p>}
  </section>;
}

export function ComparisonReviewSteps({ study, comparisonId }: { study: Study; comparisonId: string }) {
  if (!getComparisonSettings(study, comparisonId)?.cadenceChanged) return null;
  return <section className={styles.schedule} aria-label="프로그램의 점검 과정">
    <h2>4주·8주마다 프로그램이 하는 일</h2>
    <p>보유할 종목과 금액을 다시 계산하는 간격입니다. 투자 종료일이 아닙니다.</p>
    <ol className={styles.steps}>
      <li><span aria-hidden="true">1</span><div><strong>새 목표 계산</strong><p>A종목 목표: 20만원</p></div></li>
      <li><span aria-hidden="true">2</span><div><strong>현재 금액과 비교</strong><p>A종목 현재: 30만원</p></div></li>
      <li><span aria-hidden="true">3</span><div><strong>조건에 따라 결정</strong><p>일부 매도 판단 / 차이가 작으면 유지</p></div></li>
    </ol>
    <p className={styles.note}>설명용 가상 예시입니다. 매매가 필요하면 이후 거래 가능한 가격·수량 조건을 따릅니다. 위험 대응 매도는 정기 점검 사이에도 가능합니다.</p>
  </section>;
}
