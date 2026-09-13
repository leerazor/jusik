"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/research", label: "연구 개요", matches: (path: string) => path === "/research" },
  { href: "/research/progress", label: "성과·진행", matches: (path: string) => path.startsWith("/research/progress") },
  { href: "/research/forward", label: "가상 관찰", matches: (path: string) => path.startsWith("/research/forward") },
  { href: "/research/history", label: "개발 기록", matches: (path: string) => path.startsWith("/research/history") },
  { href: "/research/lab", label: "연구 도구", matches: (path: string) => path === "/research/lab" || /^\/research\/[a-zA-Z0-9_-]+$/.test(path) },
  { href: "/research/portfolio", label: "포트폴리오 비교", matches: (path: string) => path.startsWith("/research/portfolio") },
  { href: "/research/actions", label: "기업행동 자료", matches: (path: string) => path.startsWith("/research/actions") },
];

export function ResearchNavigation() {
  const pathname = usePathname();
  return (
    <nav className="research-nav" aria-label="연구 메뉴">
      {items.map((item) => (
        <Link href={item.href} aria-current={item.matches(pathname) ? "page" : undefined} key={item.href}>
          {item.label}
        </Link>
      ))}
      <Link href="/" className="research-account-link">계좌 현황</Link>
    </nav>
  );
}
