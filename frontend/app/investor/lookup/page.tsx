import { redirect } from "next/navigation";

type Props = { searchParams: Promise<{ market?: string; symbol?: string }> };

export default async function InvestorLookup({ searchParams }: Props) {
  const query = await searchParams;
  const market = query.market === "US" ? "US" : query.market === "KR" ? "KR" : null;
  const symbol = query.symbol?.trim() ?? "";
  if (!market || !/^[A-Za-z0-9.-]{1,16}$/.test(symbol)) redirect("/investor");
  redirect(`/investor/${market}/${encodeURIComponent(symbol)}`);
}
