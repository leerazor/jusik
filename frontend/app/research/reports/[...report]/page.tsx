import Link from "next/link";
import { parseResearchReportTarget, readResearchReport, researchReportHref, type ResearchReportResult } from "@/lib/research-reports";
import { renderResearchReport } from "../report-markdown";
import styles from "../reports.module.css";

export const dynamic = "force-dynamic";

const errors: Record<Exclude<ResearchReportResult["status"], "available">, string> = {
  missing: "보고서를 찾을 수 없습니다. 주소가 허용된 보고서인지 확인하세요.",
  empty: "보고서 본문이 비어 있습니다. 연구 결과가 없다는 의미는 아닙니다.",
  unavailable: "보고서 자료에 연결할 수 없습니다. 잠시 후 이 페이지를 다시 열어 주세요.",
  integrity_error: "보고서 내용이 등록된 식별 정보와 일치하지 않아 본문을 표시하지 않습니다.",
  invalid_text: "보고서의 문자 형식을 확인할 수 없어 본문을 표시하지 않습니다.",
};

export default async function ResearchReportPage({ params }: { params: Promise<{ report: string[] }> }) {
  const { report } = await params;
  const target = parseResearchReportTarget(report);
  const result = target ? await readResearchReport(target) : { status: "missing" as const };
  if (!target || result.status !== "available") return <main className={styles.main}><section className={styles.error} role="alert"><p className={styles.kicker}>연구 보고서</p><h1>보고서를 읽을 수 없습니다</h1><p>{errors[result.status === "available" ? "missing" : result.status]}</p><div className={styles.links}>{target && <a href={researchReportHref(target)}>웹에서 다시 읽기</a>}<Link href="/research/progress">연구 결과로 돌아가기</Link><Link href="/research/history">연구 기록 보기</Link></div></section></main>;
  const { body, headings } = renderResearchReport(result.markdown, target);
  const origin = { history: "공개 연구 이력", portfolio: "포트폴리오 모의 연구", dividends: "배당 포함 모의 연구", reference: "연구 참고 자료" }[target.kind];
  return <main className={styles.main}>
    <header className={styles.header}><div><p className={styles.kicker}>{origin}</p><h1>연구 보고서 읽기</h1><p>원문 전체를 이 페이지에서 읽습니다. 아래 본문의 수치와 표현은 원문을 유지했습니다.</p></div><Link href="/research/progress">연구 결과로 돌아가기 ↗</Link></header>
    <section className={styles.context} aria-label="보고서 읽기 안내"><p><strong>연구 설정에 대한 보고서입니다.</strong> 본문의 기준·후보는 시뮬레이션에서 비교한 설정이며, 사용자가 과거에 투자한 방식이나 현재 보유 내역을 뜻하지 않습니다.</p><p>4주·8주는 각각 28일·56일(달력 기준)마다 종목별 투자 비중을 다시 검토하는 간격입니다. 투자기간이나 반드시 사고파는 주기가 아닙니다. 목표 비중과 실제 비중의 차이 등 거래 조건에 따라 매매를 건너뛰며, 위험 방어를 위한 매도는 그 사이에도 발생할 수 있습니다.</p><details><summary>변동성 목표와 계산 기준 더 보기</summary><p>연 변동성 목표는 연간 수익률의 흔들림을 조절하는 설정입니다. 약속된 수익률이나 최대 손실 한도가 아닙니다. 보고서마다 다른 설정을 사용하므로 개별 보고서의 조건을 함께 읽으세요.</p><p>과거 연구 엔진의 정기 검토는 연구 시작일 당일 또는 그 이후 첫 월요일 UTC를 기준으로 계산합니다. 여러 설정을 함께 바꾼 비교는 주기 하나만의 효과로 해석할 수 없습니다.</p></details></section>
    <div className={styles.layout}>
      {headings.length > 0 && <nav className={styles.contents} aria-label="보고서 목차"><strong>목차</strong><ol>{headings.map((heading) => <li key={heading.id} data-depth={heading.depth}><a href={`#${heading.id}`}>{heading.text || "제목 없는 절"}</a></li>)}</ol></nav>}
      <article className={styles.body} aria-label="보고서 원문">{body}</article>
    </div>
    <footer className={styles.source}><strong>원문 확인 정보</strong><p>{origin}에서 읽은 전체 본문입니다. {target.kind === "history" ? "원문 바이트가 공개 기록의 SHA-256과 일치함을 확인했습니다." : "실행 식별자는 보고서 내용의 해시와 다릅니다. 아래 해시는 현재 읽은 본문의 확인 값입니다."}</p><details><summary>자료 식별 정보</summary><dl><dt>자료 종류</dt><dd>{target.kind}</dd><dt>자료 식별자</dt><dd>{target.kind === "reference" ? target.name : target.id}</dd><dt>본문 SHA-256</dt><dd>{result.sha256}</dd></dl></details><Link href="/research/history">연구 기록에서 다른 보고서 읽기 ↗</Link></footer>
  </main>;
}
