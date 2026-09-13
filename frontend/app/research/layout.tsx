import Link from "next/link";
import { ResearchNavigation } from "./research-navigation";

export default function ResearchLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <a className="skip-link" href="#research-content">본문으로 건너뛰기</a>
      <div className="research-shell">
        <header className="research-header">
          <Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">투자 판단 자료</span></Link>
          <ResearchNavigation />
        </header>
        <div id="research-content">{children}</div>
      </div>
    </>
  );
}
