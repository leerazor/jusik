import mandate from "../../docs/research-mandate.json";
import type { Study } from "./research-progress";

export type StudyNarrative = {
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
    sourceSha256: "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825",
    resultSha256: "019a2dc72dc720db5b0bbd818569e737569779abfe6db824229dc12757f805a7",
    reportArtifactSha256: "a2cbd8ad38472f3f5e32c2a300bd4a3c7edd9d7d45d9db050d3aff9bd548a535",
    question: "고정된 32개 결과를 다시 읽어 4주·8주 운용 중 무엇을 우선 검토할지 판단할 수 있는가?",
    relatedGoals: ["잦은 거래 지양", "실제 순수익·낙폭·거래 횟수·거래/FX 비용을 함께 비교", "사용자가 결과를 보고 우선순위 결정"],
    baselineRules: ["연 변동성 목표 15%", "4주마다 재조정", "비용 1x·3x"],
    candidateRules: ["연 변동성 목표 15%", "8주마다 재조정", "비용 1x·3x"],
    fixedConditions: ["기존 32개 평가와 동일한 종목·기간·자료", "초기 자본 1억원·중간 인출 없음", "전체 관측 NAV running peak MDD", "거래 fill과 UTC 거래일을 분리"],
    limitations: ["새 시뮬레이션이 아닌 고정 historical JSON의 재분석입니다.", "Continuous는 2024-04-24~2026-09-08로 요청 3년보다 짧고 PIT 완전성을 인증하지 않았습니다.", "가격만 사용해 배당·세금을 제외했습니다."],
    sourceReference: "a2cbd8ad38472f3f5e32c2a300bd4a3c7edd9d7d45d9db050d3aff9bd548a535.md",
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

export function candidateRuleForComparison(study: Study, comparisonId: string): CandidateRule | null {
  if (study.id !== "core10-low-cash" || !getStudyNarrative(study)) return null;
  const id = comparisonId.endsWith("-c2") ? "B" : comparisonId.endsWith("-c1") ? "A" : null;
  if (!id) return null;
  return { id, label: `후보 ${id} · ${id === "A" ? "밴드 2%p" : "밴드 4%p"}`, mapping: "후보 A = 밴드 2%p · 후보 B = 밴드 4%p" };
}
