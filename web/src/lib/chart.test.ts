import { describe, expect, it } from "vitest";

import { niceTicks, priceAt, stepPath, timeTicks, toSeries } from "./chart";

describe("niceTicks", () => {
  it("picks round numbers just around the prices", () => {
    expect(niceTicks(1199, 1299)).toEqual([1175, 1200, 1225, 1250, 1275, 1300]);
    expect(niceTicks(950, 2000)).toEqual([750, 1000, 1250, 1500, 1750, 2000]);
    expect(niceTicks(470.5, 470.5).every((tick) => tick >= 0)).toBe(true);
  });

  it("gives a flat line some room", () => {
    const ticks = niceTicks(999, 999);
    expect(ticks[0]).toBeLessThan(999);
    expect(ticks.at(-1)).toBeGreaterThan(999);
  });
});

describe("the price lines", () => {
  const [amazon] = toSeries([
    {
      listing_id: 1,
      site: "amazon",
      prices: [
        { checked_at: "2026-11-03T03:30:00Z", price: 1399, in_stock: true },
        { checked_at: "2026-11-04T03:30:00Z", price: 1399, in_stock: false },
        { checked_at: "2026-11-05T03:30:00Z", price: 1299, in_stock: true },
      ],
    },
  ]);
  const t = (iso: string) => Date.parse(iso);

  it("turns the history into lines, with no price where it couldn't be bought", () => {
    expect(amazon.label).toBe("Amazon");
    expect(amazon.points.map((point) => point.price)).toEqual([1399, null, 1299]);
  });

  it("holds each price until the next check, and breaks where it was sold out", () => {
    const x = (time: number) => (time - t("2026-11-03T03:30:00Z")) / 3600_000;    // hours since the first check
    const y = (price: number) => price / 100;
    expect(stepPath(amazon.points, x, y)).toBe("M0.0,14.0H24.0M48.0,13.0");
  });

  it("reads the price a line showed at any moment", () => {
    expect(priceAt(amazon, t("2026-11-03T12:00:00Z"))?.price).toBe(1399);
    expect(priceAt(amazon, t("2026-11-04T12:00:00Z"))?.price).toBeNull();
    expect(priceAt(amazon, t("2026-11-01T00:00:00Z"))).toBeUndefined();
  });

  it("puts dates along the bottom, without repeating one", () => {
    const ticks = timeTicks(t("2026-11-01T00:00:00Z"), t("2026-11-30T00:00:00Z"), 600);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
    expect(new Set(ticks.map((tick) => tick.label)).size).toBe(ticks.length);
    expect(timeTicks(5, 5, 600)).toHaveLength(1);
  });
});
