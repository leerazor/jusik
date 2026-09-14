"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/investor", label: "투자자 워크플로", matches: (path: string) => path.startsWith("/investor") },
  { href: "/research", label: "연구 개요", matches: (path: string) => path === "/research" },
  { href: "/research/progress", label: "성과 비교", matches: (path: string) => path.startsWith("/research/progress") || path.startsWith("/research/validation") },
  { href: "/research/forward", label: "가상 관찰", matches: (path: string) => path.startsWith("/research/forward") },
  { href: "/research/market", label: "시장 PIT 연구", matches: (path: string) => path.startsWith("/research/market") },
  { href: "/research/history", label: "근거 기록", matches: (path: string) => path.startsWith("/research/history") },
  { href: "/research/lab", label: "연구 도구", matches: (path: string) => path === "/research/lab" || path.startsWith("/research/portfolio") || path.startsWith("/research/actions") || (/^\/research\/[a-zA-Z0-9_-]+$/.test(path) && !["/research/progress", "/research/forward", "/research/history", "/research/validation"].includes(path)) },
];

export function ResearchNavigation() {
  const pathname = usePathname();
  return (<>
    <nav className="research-nav" aria-label="연구 메뉴">
      {items.map((item) => (
        <Link href={item.href} aria-current={item.matches(pathname) ? "page" : undefined} key={item.href}>
          {item.label}
        </Link>
      ))}
    </nav>
    <Link href="/" className="research-account-link">계좌 현황</Link>
  </>);
}
