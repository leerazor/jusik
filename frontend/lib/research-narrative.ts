import mandate from "../../docs/research-mandate.json";
import type { ResearchProgress, Study } from "./research-progress";

export type StudyNarrative = {
  reading: {
    question: string;
    baseline: string;
    candidate: string;
    example: string;
    result: string;
    nextCheck: string;
  };
  question: string;
  relatedGoals: string[];
  baselineRules: string[];
  candidateRules: string[];
  fixedConditions: string[];
  limitations: string[];
  sourceReference: string;
  conclusion: string;
};

export type CandidateRule = {
  id: "A" | "B";
  label: string;
  mapping: string;
};

type KnownStudy = StudyNarrative & {
  id: string;
  sourceSha256: string;
  resultSha256: string;
  reportArtifactSha256: string;
};

const knownStudies: readonly KnownStudy[] = [
  {
    id: "core10-low-cash",
    reading: {
      question: "주식에 더 많은 돈을 넣고, 사고팔지 다시 판단하는 간격을 늘리면 어떨까요?",
      baseline: "전체 돈의 최대 60%까지 투자할 수 있게 하고, 4주마다 보유할 종목과 금액을 다시 계산합니다.",
      candidate: "최대 95%까지 투자할 수 있게 하고, 다시 계산하는 간격을 8주로 늘렸습니다. 가격 변동에 따라 투자금을 줄이는 기준도 완화했습니다.",
      example: "설명용으로 100만원이 있다면, 첫 시험은 최대 60만원, 바꾼 시험은 최대 95만원까지 투자할 수 있습니다. 한도이므로 실제로 넣는 돈은 이보다 적을 수 있습니다.",
      result: "이 과거 자료에서는 수익이 늘었지만, 중간에 떨어진 폭과 거래 비용도 커졌습니다. 실제 투자에 쓸 방식으로 선택하지는 않았습니다.",
      nextCheck: "다른 기간에도 수익 증가와 하락·비용 증가가 함께 나타나는지 확인하세요. 수익이 더 높다는 이유만으로 더 좋은 방법이라고 정할 수 없습니다.",
    },
    sourceSha256: "090944bb3f224e5dd1ff857a9376707fc8049ff24df945a3428208969ac81342",
    resultSha256: "71c1e5efac632d6f934d5b411d5f217131d0eb635aae121e90aee0373963e445",
    reportArtifactSha256: "aceef65a6cf64ac8afddfcc0226827ce3146100651706f2e3cab010008dc70fd",
    question: "현금 대기를 줄이고 재조정 간격을 늘리면 위험과 거래 부담을 함께 관리할 수 있는가?",
    relatedGoals: ["불필요한 현금 대기 축소", "최고점 대비 낙폭 20% 안에서 관리", "거래 빈도·비용과 순수익을 함께 평가"],
    baselineRules: ["투자 상한 60%", "연 변동성 목표 10%", "4주마다 재조정", "보유 비중 밴드 2%p", "에피소드 손실 제한 10%"],
    candidateRules: ["투자 상한 95%", "연 변동성 목표 30%", "8주마다 재조정", "후보 A/B의 보유 비중 밴드 2%p 또는 4%p", "에피소드 손실 제한 10%"],
    fixedConditions: ["종목별 상한 20%·레버리지 상품 합산 상한 20%", "초기 자본 1억원·중간 인출 없음", "동일한 종목·가격 자료·비용 배수", "전역 목표는 초기 자본 포함 최고점 대비 평가액 낙폭 20%"],
    limitations: ["여러 규칙을 함께 바꾼 변경 묶음의 결과라 개별 규칙의 인과를 분리할 수 없습니다.", "과거 가격 자료를 재사용했고 시점 검증이 아닙니다.", "배당·세금은 포함하지 않았으며 독립 기간의 재현 검증이 필요합니다."],
    sourceReference: "aceef65a6cf64ac8afddfcc0226827ce3146100651706f2e3cab010008dc70fd.md:39-51",
    conclusion: "이번 과거 평가에서 두 후보가 위험 기준을 통과했지만, 후보 채택 결정은 기록되어 있지 않습니다.",
  },
  {
    id: "gross-cap",
    reading: {
      question: "주식에 넣을 수 있는 돈의 한도를 늘리면 결과가 좋아질까요?",
      baseline: "전체 돈의 최대 60%까지 투자할 수 있게 했습니다.",
      candidate: "다른 규칙은 유지하고, 투자할 수 있는 한도만 80%로 높였습니다.",
      example: "설명용 100만원이라면 최대 60만원 대신 최대 80만원까지 투자할 수 있게 한 시험입니다. 반드시 그 금액을 전부 투자한다는 뜻은 아닙니다.",
      result: "한도만 높여서는 남는 현금을 줄이면서 수익·하락 위험·비용을 함께 개선하지 못했습니다.",
      nextCheck: "한도와 실제 투자액은 다릅니다. 현금이 정말 줄었는지와 하락·비용까지 함께 확인하세요.",
    },
    sourceSha256: "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825",
    resultSha256: "8e204f3798db53eeb01859e1644bea7ba0f1cf294c22f6942ecced2b8263813d",
    reportArtifactSha256: "00329866f0dbabdd25f717ae6f8a1b3d77eabd2c4159bc8a59b6ad76b459f5aa",
    question: "투자 상한을 60%에서 80%로 높이면 현금 대기와 결과가 개선되는가?",
    relatedGoals: ["불필요한 현금 대기 축소", "낙폭과 비용을 함께 관리"],
    baselineRules: ["투자 상한 60%"],
    candidateRules: ["투자 상한 80%"],
    fixedConditions: ["변경 외 진입 규칙·보유 밴드 4%p·4주 재조정·변동성 목표 10%", "종목별 상한 20%·레버리지 상품 합산 상한 20%", "초기 자본 1억원·중간 인출 없음", "동일한 과거 자료의 정확 비교"],
    limitations: ["고정된 과거 비교에서 현금 대기 감소와 수익·위험·거래비용의 전반적 개선을 확인하지 못했습니다.", "과거 가격 자료를 재사용했고 배당·세금은 제외했습니다."],
    sourceReference: "00329866f0dbabdd25f717ae6f8a1b3d77eabd2c4159bc8a59b6ad76b459f5aa.md:1-7",
    conclusion: "투자 상한 확대가 전반적 개선을 보이지 않은 결과로 종료했습니다.",
  },
  {
    id: "volatility-target",
    reading: {
      question: "가격이 흔들릴 때 투자금을 덜 줄이면 수익과 위험은 어떻게 달라질까요?",
      baseline: "최근 가격의 흔들림을 계산해 투자금을 줄입니다. 이 조절에 쓰는 목표값은 10%입니다.",
      candidate: "목표값을 15%로 높여, 같은 가격 흔들림에서도 투자금을 덜 줄일 수 있게 했습니다. 전체 투자 한도는 60%로 같습니다.",
      example: "설명용으로, 가격이 크게 오르내려 프로그램이 투자금을 줄이려는 상황을 생각해 보세요. 목표값을 높이면 줄이는 정도가 작아질 수 있습니다. 15% 수익을 얻거나 손실을 15%로 막는다는 뜻은 아닙니다.",
      result: "남는 현금은 줄고 수익은 늘었지만, 중간 하락과 사고파는 규모·비용도 커졌습니다.",
      nextCheck: "더 번 돈만 보지 말고, 그 과정에서 더 큰 하락과 비용을 겪었는지 함께 읽으세요.",
    },
    sourceSha256: "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825",
    resultSha256: "1487e612d747cb960d20065ac3a6ce780d07136f40d80af67600c14682d1ff91",
    reportArtifactSha256: "400bfe573024b6c81fe9893a94954ee79fb8eb6e8541973b115d797c32839099",
    question: "변동성 목표를 10%에서 15%로 높이면 현금 대기를 줄이면서 위험을 감당할 수 있는가?",
    relatedGoals: ["불필요한 현금 대기 축소", "낙폭 20% 목표", "비용과 순수익을 함께 평가"],
    baselineRules: ["연 변동성 목표 10%"],
    candidateRules: ["연 변동성 목표 15%"],
    fixedConditions: ["투자 상한 60%·진입 규칙·보유 밴드 4%p·4주 재조정", "종목별 상한 20%·레버리지 상품 합산 상한 20%", "에피소드 손실 제한 10%", "초기 자본 1억원·중간 인출 없음"],
    limitations: ["현금·순수익 개선과 전체 관측 시점의 낙폭·회전율·비용 증가가 함께 관측되었습니다.", "과거 자료 비교이며 배당·세금과 미래 성과를 포함하지 않습니다.", "추가 후보 탐색이나 정책 승격은 하지 않았습니다."],
    sourceReference: "400bfe573024b6c81fe9893a94954ee79fb8eb6e8541973b115d797c32839099.md:1-10",
    conclusion: "현금과 순수익의 개선에 위험·비용 증가가 함께 나타난 상충 결과입니다.",
  },
  {
    id: "volatility15-cadence-5270",
    reading: {
      question: "사고팔지 다시 판단하는 간격을 늘리면 거래 부담을 줄일 수 있을까요?",
      baseline: "4주마다 프로그램이 보유할 종목과 금액을 다시 계산합니다.",
      candidate: "다른 규칙은 유지하고, 다시 계산하는 간격만 8주로 늘렸습니다.",
      example: "첫 점검을 마친 뒤, 첫 시험은 4주 후에 다시 계산하고 바꾼 시험은 8주 후에 다시 계산합니다. 그날 꼭 거래하는 것은 아니며, 위험에 대응하는 매도는 그 사이에도 가능합니다.",
      result: "8주 간격에서는 거래와 비용이 줄었지만, 현금으로 남는 비율은 늘고 수익과 중간 하락은 나빠졌습니다. 채택할 근거는 얻지 못했습니다.",
      nextCheck: "거래를 줄인 이점이 수익 감소와 더 큰 하락을 감수할 만큼인지가 남은 질문입니다. 이 화면에서 투자 방식을 선택할 필요는 없습니다.",
    },
    sourceSha256: "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825",
    resultSha256: "cada27b0e5518b8384e521235bc6fc1e4c5a029b9c4f8ff3db173cde41f2670d",
    reportArtifactSha256: "663ea3345b609d76f08676c56783512c943e37437a92cf06e9ac3a390d8253b8",
    question: "변동성 목표 15%에서 재조정 주기를 4주에서 8주로 늘리면 거래 부담을 낮출 수 있는가?",
    relatedGoals: ["잦은 거래 지양", "거래비용과 순수익을 함께 평가", "낙폭 20% 목표"],
    baselineRules: ["연 변동성 목표 15%", "4주마다 재조정"],
    candidateRules: ["연 변동성 목표 15%", "8주마다 재조정"],
    fixedConditions: ["투자 상한 60%·진입 규칙·보유 밴드 4%p", "종목별 상한 20%·레버리지 상품 합산 상한 20%", "동일한 기존 종목·편입 기준·기간", "초기 자본 1억원·중간 인출 없음"],
    limitations: ["8주 주기는 거래수와 비용을 줄였지만 현금 비율·순수익·전체 관측 시점의 낙폭이 악화되었습니다.", "현금 금액과 현금 비율은 평가액 분모가 달라 같은 방향으로 해석할 수 없습니다.", "과거 자료이고 3년보다 짧은 구간과 시점 검증 전 자료라는 한계가 있습니다."],
    sourceReference: "663ea3345b609d76f08676c56783512c943e37437a92cf06e9ac3a390d8253b8.md:1-16",
    conclusion: "거래 부담의 상충은 관측했지만 채택 근거를 만들지 못했습니다.",
  },
  {
    id: "cadence-decision-20260913",
    reading: {
      question: "4주와 8주 중 어느 점검 간격이 나은지, 이전 결과를 다시 읽어 판단할 수 있을까요?",
      baseline: "4주마다 보유할 종목과 금액을 다시 계산했던 시험 결과를 읽습니다.",
      candidate: "8주마다 다시 계산했던 결과를 같은 기간·비용 조건끼리 비교합니다. 새로 실행한 시험은 아닙니다.",
      example: "같은 시험 성적표를 다른 관점으로 다시 읽는 일입니다. 이전 32개 결과를 재분석했으므로 독립된 새 증거가 추가된 것은 아닙니다.",
      result: "수익·중간 하락·거래 부담에서 유불리가 엇갈렸습니다. 어느 간격을 먼저 쓰거나 채택할지 결정하지 않았습니다.",
      nextCheck: "기간과 비용 조건이 같은 행끼리 읽으세요. 한 가지 수치만으로 4주나 8주를 선택할 수 있는 결과는 아닙니다.",
    },
    sourceSha256: "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825",
    resultSha256: "019a2dc72dc720db5b0bbd818569e737569779abfe6db824229dc12757f805a7",
    reportArtifactSha256: "a2cbd8ad38472f3f5e32c2a300bd4a3c7edd9d7d45d9db050d3aff9bd548a535",
    question: "고정된 32개 결과를 다시 읽어 4주·8주마다 보유 비중을 검토하는 설정 중 무엇을 우선 검토할지 판단할 수 있는가?",
    relatedGoals: ["잦은 거래 지양", "실제 순수익·낙폭·거래 횟수·거래/FX 비용을 함께 비교", "사용자가 결과를 보고 우선순위 결정"],
    baselineRules: ["연 변동성 목표 15%", "4주마다 재조정", "비용 1x·3x"],
    candidateRules: ["연 변동성 목표 15%", "8주마다 재조정", "비용 1x·3x"],
    fixedConditions: ["기존 32개 평가와 동일한 종목·기간·자료", "초기 자본 1억원·중간 인출 없음", "전체 관측 NAV running peak MDD", "거래 fill과 UTC 거래일을 분리"],
    limitations: ["새 시뮬레이션이 아닌 고정 historical JSON의 재분석입니다.", "Continuous는 2024-04-24~2026-09-08로 요청 3년보다 짧고 PIT 완전성을 인증하지 않았습니다.", "가격만 사용해 배당·세금을 제외했습니다."],
    sourceReference: "a2cbd8ad38472f3f5e32c2a300bd4a3c7edd9d7d45d9db050d3aff9bd548a535.md:1",
    conclusion: "4주와 8주의 순수익·낙폭·거래 부담이 엇갈려 우선순위나 정책 채택을 기록하지 않았습니다.",
  },
];

export const mandateSummary = {
  capitalKrw: mandate.capital_krw,
  drawdown: mandate.maximum_drawdown_fraction,
  drawdownReference: mandate.drawdown_reference,
  leverage: mandate.leveraged_allocation_fraction,
  horizon: mandate.investment_horizon,
  lookbackYears: mandate.historical_lookback_years,
  turnoverPreference: mandate.turnover_preference,
  signalDetection: mandate.signal_detection,
  liveTrading: mandate.live_trading,
  frozenPaper: mandate.frozen_paper_contract,
  universeExpansion: mandate.research_universe_expansion,
  interimWithdrawals: mandate.interim_withdrawals,
  shortHistoryPolicy: mandate.short_history_etf_policy,
  investmentHorizonLabel: mandate.investment_horizon === "open_ended" ? "정해진 종료 없음 · 계속 운용" : "미정",
  comparisonPreference: mandate.turnover_preference.includes("side by side")
    ? "잦은 거래를 피하면서 순수익·낙폭·거래 횟수·거래/FX 비용을 나란히 비교한 뒤 우선순위를 결정"
    : mandate.turnover_preference,
} as const;

export function getStudyNarrative(study: Study): StudyNarrative | null {
  const known = knownStudies.find((item) => item.id === study.id);
  if (!known || study.source_sha256 !== known.sourceSha256 || study.result_sha256 !== known.resultSha256 || study.report_artifact_sha256 !== known.reportArtifactSha256) return null;
  return known;
}

export function compareNarrativeIdentity(study: Study): boolean {
  return getStudyNarrative(study) !== null;
}

export function findReportStudy(progress: ResearchProgress | null, artifactId: string): Study | null {
  if (progress?.research.availability !== "available") return null;
  return progress.research.studies.find((study) => study.report_artifact_sha256 === artifactId && getStudyNarrative(study) !== null) ?? null;
}

export function candidateRuleForComparison(study: Study, comparisonId: string): CandidateRule | null {
  if (study.id !== "core10-low-cash" || !getStudyNarrative(study)) return null;
  const id = comparisonId.endsWith("-c2") ? "B" : comparisonId.endsWith("-c1") ? "A" : null;
  if (!id) return null;
  return { id, label: `후보 ${id} · ${id === "A" ? "밴드 2%p" : "밴드 4%p"}`, mapping: "후보 A = 밴드 2%p · 후보 B = 밴드 4%p" };
}

export const researchSettingLabels = {
  baseline: "연구용 비교 설정",
  candidate: "변경해서 시험한 설정",
} as const;

export const researchCadenceExplanation = "4주·8주는 각각 28일·56일(달력 기준)마다 종목별로 돈을 나눠 넣는 비중을 다시 검토하는 간격입니다. 투자기간이나 반드시 사고파는 주기가 아닙니다. 비중 차이가 작은 경우 등에는 거래를 건너뛰고, 위험 방어를 위한 매도는 그 사이에도 발생할 수 있습니다.";

export type ComparisonSettings = {
  baselineRules: string[];
  candidateRules: string[];
  cadenceChanged: boolean;
  multipleChanges: boolean;
};

export function getComparisonSettings(study: Study, comparisonId: string): ComparisonSettings | null {
  const narrative = getStudyNarrative(study);
  if (!narrative || !study.comparisons.some((item) => item.id === comparisonId)) return null;
  const rule = candidateRuleForComparison(study, comparisonId);
  if (study.id === "core10-low-cash" && !rule) return null;
  const explainRule = (value: string): string => value.replace("투자 상한 ", "전체 돈 중 투자할 수 있는 한도 ").replace("4주마다 재조정", "4주(28일)마다 종목별 투자 비중 점검").replace("8주마다 재조정", "8주(56일)마다 종목별 투자 비중 점검");
  return {
    baselineRules: narrative.baselineRules.map(explainRule),
    candidateRules: narrative.candidateRules.map((value) => explainRule(value.startsWith("후보 A/B") && rule ? `보유 비중 밴드 ${rule.id === "A" ? "2" : "4"}%p · 후보 ${rule.id}` : value)),
    cadenceChanged: ["core10-low-cash", "volatility15-cadence-5270", "cadence-decision-20260913"].includes(study.id),
    multipleChanges: study.id === "core10-low-cash",
  };
}

export function researchStudyTitle(study: Study): string {
  if (!getStudyNarrative(study)) return study.title;
  return study.title.replace(/4주[·/]8주 운용/g, "4주·8주 보유 비중 검토");
}

export function researchSettingName(study: Study, label: string): string {
  if (!getStudyNarrative(study)) return label;
  return label.replace(/([48])주 운용/g, "$1주마다 보유 비중 검토");
}
