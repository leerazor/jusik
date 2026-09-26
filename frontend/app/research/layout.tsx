import Link from "next/link";
import type { Metadata } from "next";
import { ResearchNavigation } from "./research-navigation";

export const metadata: Metadata = { title: "Jusik · 투자 연구", description: "투자 목표와 연구 근거를 확인하는 화면" };

export default function ResearchLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <a className="skip-link" href="#research-content">본문으로 건너뛰기</a>
      <div className="research-shell">
        <header className="research-header">
          <Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">투자 연구</span></Link>
          <ResearchNavigation />
        </header>
        <div id="research-content">{children}</div>
      </div>
    </>
  );
}
