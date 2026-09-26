import assert from "node:assert/strict";
import { comparisonBars } from "../lib/research-chart";

const positive = comparisonBars("25", "100");
assert.equal(positive.zero, 0);
assert.equal(positive.bars[0]?.width, 25);
assert.equal(positive.bars[1]?.width, 100);
const negative = comparisonBars("-10", "20");
assert.ok(negative.zero > 0 && negative.zero < 100);
assert.equal(negative.bars[0]?.left, 0);
assert.equal(negative.bars[1]?.left, negative.zero);
assert.equal(negative.bars[0]?.width, negative.zero);
const losses = comparisonBars("-100", "-50");
assert.equal(losses.zero, 100);
assert.equal(losses.bars[1]?.left, 50);
assert.deepEqual(comparisonBars("0", "-0").bars, [{ left: 0, width: 0 }, { left: 0, width: 0 }]);
assert.equal(comparisonBars("20", "20").bars[0]?.width, comparisonBars("20", "20").bars[1]?.width);
assert.ok(Math.abs(comparisonBars("0.000001", "1").bars[0]!.width - 0.0001) < Number.EPSILON);
assert.deepEqual(comparisonBars(undefined, null).bars, [null, null]);
for (const bad of ["", " ", "NaN", "Infinity", "1e309", "<script>"]) assert.equal(comparisonBars(bad, "1").bars[0], null);
assert.equal(comparisonBars(null, "10").bars[1]?.width, 100);
for (const [a, b] of [["-1e308", "1e308"], ["1e-300", "2e-300"], ["0", "1e308"], ["-99.99", "0.000001"]]) {
  const result = comparisonBars(a, b);
  assert.ok(Number.isFinite(result.zero) && result.zero >= 0 && result.zero <= 100);
  for (const bar of result.bars) {
    assert.ok(bar && Number.isFinite(bar.left) && Number.isFinite(bar.width));
    assert.ok(bar.left >= 0 && bar.width >= 0 && bar.left + bar.width <= 100.000001);
  }
}
console.log("Research chart checks passed: signed values, shared axes, zero, equal, tiny, extreme and missing inputs.");
