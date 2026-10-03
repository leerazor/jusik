import type { Metadata } from "next";
import Link from "next/link";
import { researchBackendUrl } from "@/lib/research";
import { approvedUniverseSchema, type ApprovedUniverse } from "./contract";
import { refreshApprovedReadiness } from "./actions";
import { ApprovedUniverseEditor } from "./editor";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "비교할 종목 등록 · Jusik" };
export const dynamic = "force-dynamic";

export default async function ApprovedUniversePage() {
  let snapshot: ApprovedUniverse | null = null;
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/approved-universe`, {
      cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (response.ok) snapshot = approvedUniverseSchema.parse(await response.json());
  } catch { /* Read failure is shown below; never imply an empty approved list. */ }
  const readiness = snapshot ? await refreshApprovedReadiness() : null;
  return <main className={styles.main}>
    <p className={styles.eyebrow}>새 연구의 첫 단계</p>
    <h1>단순 보유와 비교할 종목</h1>
    <p>직접 고른 한국·미국 종목을 등록하세요. 이 목록으로 단순 보유 기준과 거래가 적은 매수·보유·매도·현금 후보를 같은 조건에서 비교할 준비를 합니다.</p>
    <p>목록 저장은 비교를 시작하지 않습니다. 지금은 아래 자료 현황을 새로고침해 확인하세요. 개발 담당자가 자료와 비용을 검증하고 평가 기간을 정한 뒤 별도로 비교를 실행할 예정입니다.</p>
    {snapshot ? <ApprovedUniverseEditor initial={snapshot} initialReadiness={readiness?.revision === snapshot.revision ? readiness : null} /> : <><p className={styles.status}>종목 등록 상태 확인 불가 · 성과 비교 준비 중 · 자동매매 미연결</p><p className={styles.error} role="alert">등록 목록을 읽지 못했습니다. 연결을 확인한 뒤 새로고침하세요. 저장은 사용할 수 없습니다.</p></>}
    <p className={styles.next}>다음 단계는 종목별 가격 이력과 배당·환율의 출처·시점·비용을 확인하는 것입니다. 이 화면의 수집 현황은 자료 적격성이나 성과 검증을 뜻하지 않습니다. 기준선과 후보의 비용 포함 비교는 아직 수행하지 않았습니다.</p>
    <Link href="/research">연구 첫 화면으로 돌아가기</Link>
  </main>;
}
