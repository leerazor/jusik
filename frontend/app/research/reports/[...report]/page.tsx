import Link from "next/link";
import { getResearchProgress } from "@/lib/research-progress";
import { findReportStudy, getStudyNarrative } from "@/lib/research-narrative";
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
  const progress = target.kind === "history" ? await getResearchProgress().catch(() => null) : null;
  const study = target.kind === "history" ? findReportStudy(progress, target.id) : null;
  const narrative = study ? getStudyNarrative(study) : null;
  const origin = { history: "공개 연구 이력", portfolio: "포트폴리오 모의 연구", dividends: "배당 포함 모의 연구", reference: "연구 참고 자료" }[target.kind];
  return <main className={styles.main}>
    <header className={styles.header}><div><p className={styles.kicker}>{origin}</p><h1>연구 보고서 읽기</h1><p>원문 전체를 이 페이지에서 읽습니다. 아래 본문의 수치와 표현은 원문을 유지했습니다.</p></div><Link href="/research/progress">연구 결과로 돌아가기 ↗</Link></header>
    <section className={styles.context} aria-label="보고서 읽기 안내">
      <h2>{narrative ? narrative.reading.question : "이 보고서는 어떤 근거를 담고 있나요?"}</h2>
      {narrative ? <><p><strong>먼저 읽을 결론</strong> {narrative.reading.result}</p><p><strong>읽으며 확인할 것</strong> {narrative.reading.nextCheck}</p><p>아래 원문에는 이 결론을 계산한 조건과 표가 있습니다. 배당·세금이 빠져 있고, 그때 알 수 없던 정보를 쓰지 않았는지도 검증 전입니다. 미래에도 같은 결과가 나온다는 증거로 읽지 마세요.</p></> : <p>{target.kind === "reference" ? "연구에서 참고한 자료입니다. 아래 목차에서 관심 있는 주제를 고르고, 본문이 어떤 자료를 근거로 설명하는지 확인하세요." : "가상의 돈으로 계산한 연구 기록입니다. 이 보고서에 연결된 쉬운 요약은 확인하지 못했습니다. 아래 원문의 목적·계산 조건·결론 순서로 읽고, 다른 연구의 설명을 이 결과에 적용하지 마세요."}</p>}
      <p>본문의 ‘기준’과 ‘후보’는 연구자가 비교한 시험을 뜻합니다. 사용자의 과거 투자나 실제 계좌 기록을 뜻하지 않습니다.</p>
      <details><summary>본문의 숫자와 용어를 읽는 방법</summary><p>‘수익률’은 시작한 돈이 얼마나 늘거나 줄었는지, ‘낙폭’은 도중에 가장 높았던 금액에서 얼마나 떨어졌는지입니다. 예를 들어 120만원에서 108만원으로 줄면 낙폭은 10%입니다. 예시는 실제 성과와 구분해 읽으세요.</p><p>‘NAV’는 현금과 보유 주식의 가치를 합한 금액입니다. ‘비중’은 그 돈 중 특정 종목이나 현금이 차지하는 몫입니다. ‘시점 검증(PIT)’은 과거 판단에 당시에는 몰랐을 정보를 쓰지 않았는지 확인하는 일입니다.</p><p>화면 요약은 소수점 셋째 자리 이하를 버리고, 원문은 작성 당시 표기를 유지합니다. 예를 들어 요약 43.17%와 원문 43.18%처럼 표시 자릿수 처리 때문에 차이가 날 수 있습니다.</p></details>
      {study && <Link href={`/research/progress#study-${study.id}`}>이 연구의 쉬운 설명과 비교 표로 돌아가기 ↗</Link>}
    </section>
    <div className={styles.layout}>
      {headings.length > 0 && <nav className={styles.contents} aria-label="보고서 목차"><strong>목차</strong><ol>{headings.map((heading) => <li key={heading.id} data-depth={heading.depth}><a href={`#${heading.id}`}>{heading.text || "제목 없는 절"}</a></li>)}</ol></nav>}
      <article className={styles.body} aria-label="보고서 원문">{body}</article>
    </div>
    <footer className={styles.source}><strong>원문 확인 정보</strong><p>{origin}에서 읽은 전체 본문입니다. {target.kind === "history" ? "원문 바이트가 공개 기록의 SHA-256과 일치함을 확인했습니다." : "실행 식별자는 보고서 내용의 해시와 다릅니다. 아래 해시는 현재 읽은 본문의 확인 값입니다."}</p><details><summary>자료 식별 정보</summary><dl><dt>자료 종류</dt><dd>{target.kind}</dd><dt>자료 식별자</dt><dd>{target.kind === "reference" ? target.name : target.id}</dd><dt>본문 SHA-256</dt><dd>{result.sha256}</dd></dl></details><Link href="/research/history">연구 기록에서 다른 보고서 읽기 ↗</Link></footer>
  </main>;
}
