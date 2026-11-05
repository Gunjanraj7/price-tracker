import { describe, expect, it } from "vitest";

import {
  formatAxisRupees,
  formatPercent,
  formatRupees,
  missingStores,
  parsePrice,
  plural,
  priceParts,
  storeName,
  timeAgo,
  timeUntil,
} from "./format";

describe("formatRupees", () => {
  it("writes prices the Indian way, with paise only when there are some", () => {
    expect(formatRupees(1299)).toBe("₹1,299");
    expect(formatRupees(470.5)).toBe("₹470.50");
    expect(formatRupees(129999)).toBe("₹1,29,999");
  });

  it("splits prices the way Amazon shows them", () => {
    expect(priceParts(129999)).toEqual({ whole: "1,29,999", paise: null });
    expect(priceParts(470.5)).toEqual({ whole: "470", paise: "50" });
    expect(priceParts(99.05)).toEqual({ whole: "99", paise: "05" });
    expect(priceParts(0.999)).toEqual({ whole: "1", paise: null });     // rounds to the paisa
  });

  it("writes percents and counts", () => {
    expect(formatPercent(12.4)).toBe("12%");
    expect(formatPercent(-7.6)).toBe("8%");
    expect(formatPercent(0.3)).toBe("<1%");
    expect(plural(1, "item")).toBe("1 item");
    expect(plural(3, "item")).toBe("3 items");
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

  it("says how long until, in words", () => {
    expect(timeUntil(before(-20_000), now)).toBe("any minute now");
    expect(timeUntil(before(-25 * 60_000), now)).toBe("in 25 minutes");
    expect(timeUntil(before(-5 * 3600_000), now)).toBe("in 5 hours");
    expect(timeUntil(before(-30 * 3600_000), now)).toBe("tomorrow");
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
