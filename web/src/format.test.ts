import { describe, expect, it } from "vitest";

import { niceTicks } from "./components/PriceHistory";
import { formatAxisRupees, formatRupees, missingStores, parsePrice, storeName, timeAgo } from "./format";

describe("formatRupees", () => {
  it("writes prices the Indian way, with paise only when there are some", () => {
    expect(formatRupees(1299)).toBe("₹1,299");
    expect(formatRupees(470.5)).toBe("₹470.50");
    expect(formatRupees(129999)).toBe("₹1,29,999");
  });

  it("shortens big numbers on chart axes", () => {
    expect(formatAxisRupees(9500)).toBe("₹9,500");
    expect(formatAxisRupees(12000)).toBe("₹12K");
    expect(formatAxisRupees(150000)).toBe("₹1.5L");
  });
});

describe("timeAgo", () => {
  const now = Date.parse("2026-11-05T12:00:00Z");
  const before = (ms: number) => new Date(now - ms).toISOString();

  it("says how long ago, in words", () => {
    expect(timeAgo(before(20_000), now)).toBe("just now");
    expect(timeAgo(before(5 * 60_000), now)).toBe("5 minutes ago");
    expect(timeAgo(before(3 * 3600_000), now)).toBe("3 hours ago");
    expect(timeAgo(before(30 * 3600_000), now)).toBe("yesterday");
  });
});

describe("parsePrice", () => {
  it("reads prices however they're typed", () => {
    expect(parsePrice("1500")).toBe(1500);
    expect(parsePrice(" ₹1,499.50 ")).toBe(1499.5);
    expect(parsePrice("Rs. 60,000")).toBe(60000);
    expect(parsePrice("")).toBeNull();
  });

  it("refuses what isn't a price", () => {
    for (const text of ["abc", "0", "-5", "10.555", "1.2.3"]) {
      expect(parsePrice(text)).toBeNaN();
    }
  });
});

describe("stores", () => {
  it("names stores and finds the ones an item is missing", () => {
    expect(storeName("amazon")).toBe("Amazon");
    expect(missingStores(["amazon"])).toEqual(["flipkart"]);
    expect(missingStores(["amazon", "flipkart"])).toEqual([]);
  });
});

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
