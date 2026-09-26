import { getComparisonSettings, getStudyNarrative, researchCadenceExplanation, researchSettingLabels } from "@/lib/research-narrative";
import type { Study } from "@/lib/research-progress";
import styles from "./comparison-settings.module.css";

export function ComparisonSettings({ study, comparisonId }: { study: Study; comparisonId: string }) {
  const settings = getComparisonSettings(study, comparisonId);
  const narrative = getStudyNarrative(study);
  return <section className={styles.settings} aria-label="비교한 연구 설정">
    <p className={styles.context}><strong>연구자가 만든 두 시험입니다.</strong> 같은 과거 주가에 서로 다른 규칙을 적용해 가상의 돈으로 사고팔았다고 계산했습니다. 사용자의 투자 이력이나 실제 계좌를 비교하는 화면이 아닙니다.</p>
    {settings && narrative ? <>
      <div className={styles.columns}>
        <div><h3>{researchSettingLabels.baseline}</h3><p>{narrative.reading.baseline}</p></div>
        <div><h3>{researchSettingLabels.candidate}</h3><p>{narrative.reading.candidate}</p></div>
      </div>
      <p className={styles.example}><strong>이해를 위한 예시</strong>{narrative.reading.example} 아래 실제 연구 결과와 구분해서 읽어 주세요.</p>
      {settings.cadenceChanged && <div className={styles.schedule}>
        <h3>4주·8주마다, 누가 무엇을 하나요?</h3>
        <p>프로그램이 그날까지의 가격 자료를 보고 <strong>어떤 종목을 얼마만큼 보유할지 다시 계산</strong>합니다. 사람에게 돈을 맡기는 기간이나 투자 종료일이 아닙니다.</p>
        <ol>
          <li><strong>새 목표를 계산합니다.</strong> 예를 들어 A종목을 20만원어치 보유하겠다고 정합니다.</li>
          <li><strong>지금 가진 금액과 비교합니다.</strong> A종목이 30만원어치라면, 차이를 줄이도록 일부 파는 결정을 할 수 있습니다.</li>
          <li><strong>거래 조건을 확인합니다.</strong> 차이가 작으면 그대로 둘 수 있습니다. 매매가 필요해도 실제 계산상 거래는 이후 거래 가능한 시점의 가격·수량 조건을 따릅니다.</li>
        </ol>
        <p className={styles.note}>20만원·30만원은 행동을 설명하는 가상의 예시이며, 이 시험의 실제 거래나 매수 권고가 아닙니다. 손실에 대응하는 매도는 정기 점검 사이에도 가능합니다.</p>
      </div>}
      {settings.multipleChanges && <p className={styles.warning}>이 시험에서는 투자 한도·가격 흔들림에 대한 대응·점검 간격을 함께 바꿨습니다. 결과가 좋아졌더라도 “8주마다 점검해서 좋아졌다”고 분리해서 결론낼 수 없습니다.</p>}
      <details className={styles.details}>
        <summary>정확한 설정값과 거래를 줄이거나 멈추는 규칙</summary>
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
