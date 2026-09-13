/** Format a decimal fraction as a percentage without converting through a float. */
export function fractionToPercent(value: string): string {
  const normalized = value.replace(/^(-?)\./, "$10.");
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(normalized);
  if (!match) return "확인할 수 없음";
  const [, sign, whole, fraction = ""] = match;
  const digits = `${whole}${fraction}`;
  const point = whole.length + 2;
  const wholePart = (point >= digits.length ? `${digits}${"0".repeat(point - digits.length)}` : digits.slice(0, point)).replace(/^0+(?=\d)/, "") || "0";
  const fractionPart = point < digits.length ? digits.slice(point).replace(/0+$/, "") : "";
  return `${sign}${wholePart}${fractionPart ? `.${fractionPart}` : ""}`;
}
