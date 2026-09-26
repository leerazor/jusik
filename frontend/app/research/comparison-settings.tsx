import { getComparisonSettings, researchCadenceExplanation, researchSettingLabels } from "@/lib/research-narrative";
import type { Study } from "@/lib/research-progress";
import styles from "./comparison-settings.module.css";

export function ComparisonSettings({ study, comparisonId }: { study: Study; comparisonId: string }) {
  const settings = getComparisonSettings(study, comparisonId);
  return <section className={styles.settings} aria-label="비교한 연구 설정">
    <p className={styles.context}><strong>두 설정 모두 연구자가 비교하려고 만든 가상 설정입니다.</strong> 과거 자료로 계산하며, 사용자의 이전 투자 방식이나 실제 보유 내역이 아닙니다.</p>
    {settings ? <>
      <div className={styles.columns}><div><h3>{researchSettingLabels.baseline}</h3><ul>{settings.baselineRules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div><div><h3>{researchSettingLabels.candidate}</h3><ul>{settings.candidateRules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div></div>
      {settings.cadenceChanged && <p className={styles.explanation}><strong>4주·8주는 무엇을 하나요?</strong> {researchCadenceExplanation}</p>}
      <p className={styles.explanation}>연 변동성 목표는 연간 수익률의 흔들림을 조절하는 설정이며, 약속된 수익률이나 최대 손실 한도가 아닙니다. 보유 비중 밴드는 목표와 실제 비중의 차이가 작을 때 거래를 건너뛰는 허용 폭입니다.</p>
      {settings.multipleChanges && <p className={styles.warning}>투자 상한·변동성 목표·검토 간격 등을 함께 바꿨습니다. 결과를 4주·8주 간격 하나만의 효과로 해석할 수 없습니다.</p>}
    </> : <p className={styles.explanation}>이 자료에 연결된 설정 설명을 확인할 수 없습니다. 특정 규칙을 추정하지 않고 검증된 수치와 원본 표기를 보여줍니다.</p>}
  </section>;
}
