import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Jusik · 나의 주식",
  description: "국내·해외 보유 주식 현황판",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
