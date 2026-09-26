"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const primaryItems = [
  { href: "/research", label: "한눈에 보기", matches: (path: string) => path === "/research" },
  { href: "/research/progress", label: "연구 결과", matches: (path: string) => path.startsWith("/research/progress") || path.startsWith("/research/validation") },
  { href: "/research/forward", label: "모의 관찰", matches: (path: string) => path.startsWith("/research/forward") },
];
const secondaryItems = [
  { href: "/investor", label: "종목 직접 연구", matches: (path: string) => path.startsWith("/investor") },
  { href: "/research/history", label: "연구 기록", matches: (path: string) => path.startsWith("/research/history") },
  { href: "/research/market", label: "시장자료 연구", matches: (path: string) => path.startsWith("/research/market") },
  { href: "/", label: "계좌 현황", matches: (path: string) => path === "/" },
];

export function ResearchNavigation() {
  const pathname = usePathname();
  const knownRoute = [...primaryItems, ...secondaryItems].some((item) => item.matches(pathname));
  return <nav className="research-nav" aria-label="연구 메뉴">
    {primaryItems.map((item) => <Link href={item.href} aria-current={item.matches(pathname) ? "page" : undefined} key={item.href}>{item.label}</Link>)}
    <details className="research-more" key={pathname}>
      <summary>더 보기</summary>
      <div className="research-more-menu">
        {secondaryItems.slice(0, 2).map((item) => <Link href={item.href} aria-current={item.matches(pathname) ? "page" : undefined} key={item.href}>{item.label}</Link>)}
        <Link href="/research/lab" aria-current={!knownRoute && pathname.startsWith("/research/") ? "page" : undefined}>연구 도구</Link>
        {secondaryItems.slice(2).map((item) => <Link href={item.href} aria-current={item.matches(pathname) ? "page" : undefined} key={item.href}>{item.label}</Link>)}
      </div>
    </details>
  </nav>;
}
