"use client";

import { useMemo, useState } from "react";
import { amount, marketNames, tone, type Holding } from "@/lib/portfolio";

export type HoldingRow = {
  accountId: string;
  accountLabel: string;
  holding: Holding;
};

type SortKey =
  | "account"
  | "stock"
  | "quantity"
  | "average"
  | "current"
  | "value"
  | "profit"
  | "return"
  | "per"
  | "pbr"
  | "eps"
  | "advice";

type SortState = { key: SortKey; direction: "ascending" | "descending" };

function decimalParts(value: string): { negative: boolean; whole: string; fraction: string } {
  const signed = value.startsWith("-");
  const unsigned = signed ? value.slice(1) : value;
  const negative = signed && /[1-9]/.test(unsigned);
  const [wholeRaw, fractionRaw = ""] = unsigned.split(".");
  return {
    negative,
    whole: wholeRaw.replace(/^0+(?=\d)/, ""),
    fraction: fractionRaw.replace(/0+$/, ""),
  };
}

export function compareDecimal(left: string, right: string): number {
  const a = decimalParts(left);
  const b = decimalParts(right);
  if (a.negative !== b.negative) return a.negative ? -1 : 1;
  const sign = a.negative ? -1 : 1;
  if (a.whole.length !== b.whole.length) return (a.whole.length - b.whole.length) * sign;
  const whole = a.whole.localeCompare(b.whole);
  if (whole !== 0) return whole * sign;
  const length = Math.max(a.fraction.length, b.fraction.length);
  return a.fraction.padEnd(length, "0").localeCompare(b.fraction.padEnd(length, "0")) * sign;
}

const numericKeys = new Set<SortKey>([
  "quantity",
  "average",
  "current",
  "value",
  "profit",
  "return",
  "per",
  "pbr",
  "eps",
]);

function sortValue(row: HoldingRow, key: SortKey): string | null {
  const holding = row.holding;
  const values: Record<SortKey, string | null> = {
    account: row.accountLabel,
    stock: `${holding.name}\u0000${holding.symbol}`,
    quantity: holding.quantity,
    average: holding.average_price_krw,
    current: holding.current_price_krw,
    value: holding.value_krw,
    profit: holding.profit_krw,
    return: holding.return_pct,
    per: holding.fundamentals.per,
    pbr: holding.fundamentals.pbr,
    eps: holding.fundamentals.eps,
    advice: holding.advice.label,
  };
  return values[key];
}

function NullableNumber({ value, suffix = "" }: { value: string | null; suffix?: string }) {
  return value === null ? <span className="unavailable">조회 불가</span> : <>{amount(value, 2)}{suffix}</>;
}

const columns: { key: SortKey; label: string }[] = [
  { key: "account", label: "계좌" },
  { key: "stock", label: "종목 / 시장" },
  { key: "quantity", label: "수량" },
  { key: "average", label: "평균매입가(원)" },
  { key: "current", label: "현재가(원)" },
  { key: "value", label: "평가금액(원)" },
  { key: "profit", label: "평가손익(원)" },
  { key: "return", label: "수익률" },
  { key: "per", label: "PER" },
  { key: "pbr", label: "PBR" },
  { key: "eps", label: "EPS(거래통화)" },
  { key: "advice", label: "규칙 평가" },
];

export function HoldingsTable({ rows }: { rows: HoldingRow[] }) {
  const [sort, setSort] = useState<SortState>({ key: "stock", direction: "ascending" });
  const sorted = useMemo(() => {
    return rows.map((row, index) => ({ row, index })).sort((left, right) => {
      const a = sortValue(left.row, sort.key);
      const b = sortValue(right.row, sort.key);
      if (a === null || b === null) {
        if (a === b) return left.index - right.index;
        return a === null ? 1 : -1;
      }
      const compared = numericKeys.has(sort.key)
        ? compareDecimal(a, b)
        : a.localeCompare(b, "ko");
      const directed = sort.direction === "ascending" ? compared : -compared;
      return directed || left.index - right.index;
    }).map(({ row }) => row);
  }, [rows, sort]);

  function changeSort(key: SortKey) {
    setSort((current) => ({
      key,
      direction:
        current.key === key && current.direction === "ascending" ? "descending" : "ascending",
    }));
  }

  return (
    <div className="table-wrap">
      <table aria-label="보유 종목">
        <caption className="sr-only">등록한 증권 계좌의 원화 환산 보유 주식</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                aria-sort={sort.key === column.key ? sort.direction : "none"}
              >
                <button className="sort-button" onClick={() => changeSort(column.key)}>
                  {column.label}
                  <span aria-hidden="true">
                    {sort.key === column.key ? (sort.direction === "ascending" ? " ↑" : " ↓") : " ↕"}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ accountId, accountLabel, holding }) => (
            <tr key={`${accountId}:${holding.market}:${holding.symbol}`}>
              <td className="account-cell">{accountLabel}</td>
              <td>
                <strong>{holding.name}</strong>
                <small>
                  {holding.symbol} · {marketNames[holding.market] ?? holding.market} · {holding.currency}
                </small>
                <small>
                  원통화 평균 {amount(holding.average_price, 4)} · 현재 {amount(holding.current_price, 4)} · 평가 {amount(holding.value, 2)} · 손익 {amount(holding.profit, 2)}
                </small>
                {holding.fx_rate && (
                  <small>
                    환율 {amount(holding.fx_rate, 4)}원 · {holding.fx_source ?? "출처 없음"}{holding.fx_as_of ? ` · ${holding.fx_as_of}` : ""}
                  </small>
                )}
              </td>
              <td>{amount(holding.quantity, 8)}</td>
              <td><NullableNumber value={holding.average_price_krw} /></td>
              <td><NullableNumber value={holding.current_price_krw} /></td>
              <td><NullableNumber value={holding.value_krw} /></td>
              <td className={tone(holding.profit_krw ?? "0")}>
                <NullableNumber value={holding.profit_krw} />
              </td>
              <td className={tone(holding.return_pct ?? "0")}>
                <NullableNumber value={holding.return_pct} suffix="%" />
              </td>
              <td><NullableNumber value={holding.fundamentals.per} /></td>
              <td><NullableNumber value={holding.fundamentals.pbr} /></td>
              <td><NullableNumber value={holding.fundamentals.eps} /></td>
              <td>
                <span className={`advice advice-${holding.advice.signal}`}>{holding.advice.label}</span>
                <small>{holding.advice.reasons.join(" ")}</small>
                {(holding.fundamentals.bps || holding.fundamentals.instrument_type) && (
                  <small>
                    {holding.fundamentals.bps ? `BPS ${amount(holding.fundamentals.bps, 2)} ${holding.currency}` : ""}
                    {holding.fundamentals.bps && holding.fundamentals.instrument_type ? " · " : ""}
                    {holding.fundamentals.instrument_type ?? ""}
                  </small>
                )}
                {holding.fundamentals.source_url && (
                  <small>
                    <a href={holding.fundamentals.source_url} target="_blank" rel="noreferrer">
                      {holding.fundamentals.source}
                    </a>{holding.fundamentals.fetched_at ? ` · ${new Date(holding.fundamentals.fetched_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}` : ""}
                  </small>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
