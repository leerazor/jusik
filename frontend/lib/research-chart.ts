type Bar = { left: number; width: number };

/** Display geometry only. Financial labels and comparisons retain decimal strings. */
export function comparisonBars(baseline: string | null | undefined, candidate: string | null | undefined): { zero: number; bars: [Bar | null, Bar | null] } {
  const parse = (value: string | null | undefined): number | null => {
    if (typeof value !== "string" || !/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value)) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const values = [parse(baseline), parse(candidate)];
  const magnitude = Math.max(...values.map((value) => Math.abs(value ?? 0)));
  // Normalize before subtracting so large values with opposite signs cannot overflow.
  const normalized = values.map((value) => value === null ? null : magnitude === 0 ? 0 : value / magnitude);
  const min = Math.min(0, ...normalized.map((value) => value ?? 0));
  const max = Math.max(0, ...normalized.map((value) => value ?? 0));
  const span = max - min || 1;
  const zero = min === 0 ? 0 : -min / span * 100;
  const bars = normalized.map((value): Bar | null => {
    if (value === null) return null;
    const point = (value - min) / span * 100;
    return { left: Math.min(point, zero), width: Math.abs(point - zero) };
  });
  return { zero, bars: [bars[0], bars[1]] };
}
