import { describe, expect, it } from "vitest";

import type { Item, Listing, ListingStats } from "./api";
import { matches, sortItems, summarize, targetProgress, targetSuggestions, totals } from "./insights";

function stats(changes: Partial<ListingStats> = {}): ListingStats {
  return { lowest_price: 900, highest_price: 1500, usual_price: 1000, previous_price: 1000, checks: 5, recent_prices: [], ...changes };
}

function listing(changes: Partial<Listing> = {}): Listing {
  return {
    id: 1,
    site: "amazon",
    product_id: "A1",
    url: "https://www.amazon.in/dp/A1",
    title: null,
    image_url: null,
    last_price: 1000,
    last_in_stock: true,
    last_checked_at: "2026-11-05T03:30:00Z",
    last_error: null,
    stats: stats(),
    ...changes,
  };
}

function item(changes: Partial<Item> = {}, listings: Partial<Listing>[] = [{}]): Item {
  return {
    id: 1,
    name: "Earbuds",
    target_price: null,
    active: true,
    created_at: "2026-11-01T00:00:00Z",
    listings: listings.map((one, i) => listing({ id: i + 1, ...one })),
    ...changes,
  };
}

const vibeAt = (price: number, more: Partial<ListingStats> = {}, target: number | null = null) =>
  summarize(item({ target_price: target }, [{ last_price: price, stats: stats(more) }])).vibe;

describe("the vibe of a price", () => {
  it("compares it with the usual price and the target", () => {
    expect(vibeAt(950, {}, 960)).toBe("target");
    expect(vibeAt(900)).toBe("lowest");              // the lowest seen, and below usual
    expect(vibeAt(880, { lowest_price: 850 })).toBe("hot");      // 12% below usual
    expect(vibeAt(950, { lowest_price: 850 })).toBe("good");     // 5% below
    expect(vibeAt(990, { lowest_price: 850 })).toBe("mid");      // 1% below
    expect(vibeAt(1010, { lowest_price: 850 })).toBe("mid");     // 1% above
    expect(vibeAt(1100, { lowest_price: 850 })).toBe("pricey");
  });

  it("waits for a few checks before judging", () => {
    expect(vibeAt(700, { checks: 1 })).toBe("new");
    expect(vibeAt(700, { usual_price: null })).toBe("new");
    expect(vibeAt(899, { lowest_price: 899, checks: 2 })).toBe("hot");    // the lowest, but too few checks to say "ever"
  });

  it("is out of stock when no store sells it", () => {
    expect(summarize(item({}, [{ last_in_stock: false, last_price: null }])).vibe).toBe("out");
  });
});

describe("an item's summary", () => {
  it("takes the cheapest store, and the lowest and highest of all", () => {
    const summary = summarize(
      item({ target_price: 1100 }, [
        { site: "amazon", last_price: 1200, stats: stats({ lowest_price: 950, highest_price: 1600 }) },
        { site: "flipkart", last_price: 1150, stats: stats({ lowest_price: 990, highest_price: 1300, previous_price: 1250 }) },
      ]),
    );
    expect(summary.best?.site).toBe("flipkart");
    expect([summary.price, summary.lowest, summary.highest]).toEqual([1150, 950, 1600]);
    expect(summary.change).toBe(-100);
    expect(summary.targetGap).toBe(50);
    expect(summary.targetHit).toBe(false);
  });

  it("needs attention when a check failed or nothing can be bought", () => {
    expect(summarize(item({}, [{ last_error: "The store refused the request." }])).needsAttention).toBe(true);
    expect(summarize(item({}, [{ last_in_stock: false }])).needsAttention).toBe(true);
    expect(summarize(item()).needsAttention).toBe(false);
  });
});

describe("totals", () => {
  it("adds up the dashboard's numbers", () => {
    const entries = [
      item({ id: 1, target_price: 1000 }, [{ last_price: 950, stats: stats({ previous_price: 990 }) }]),
      item({ id: 2 }, [{ last_price: 1100 }, { site: "flipkart", last_price: 1200 }]),
    ].map((one) => ({ item: one, summary: summarize(one) }));
    expect(totals(entries)).toEqual({ items: 2, pages: 3, targetHit: 1, dropped: 1, deals: 1, attention: 0, couldSave: 50 });
  });
});

describe("filters and sorting", () => {
  const entries = [
    item({ id: 1, name: "Pricey", created_at: "2026-11-01T00:00:00Z" }, [{ last_price: 1300, stats: stats({ lowest_price: 800 }) }]),
    item({ id: 2, name: "Deal", created_at: "2026-11-03T00:00:00Z" }, [{ last_price: 850, stats: stats({ lowest_price: 800 }) }]),
    item({ id: 3, name: "gone", created_at: "2026-11-02T00:00:00Z" }, [{ last_price: null, last_in_stock: false }]),
  ].map((one) => ({ item: one, summary: summarize(one) }));
  const names = (sorted: typeof entries) => sorted.map((entry) => entry.item.name);

  it("sorts the best deals first, and out of stock last by price", () => {
    expect(names(sortItems(entries, "deals"))).toEqual(["Deal", "Pricey", "gone"]);
    expect(names(sortItems(entries, "price-low"))).toEqual(["Deal", "Pricey", "gone"]);
    expect(names(sortItems(entries, "price-high"))).toEqual(["Pricey", "Deal", "gone"]);
    expect(names(sortItems(entries, "newest"))).toEqual(["Deal", "gone", "Pricey"]);
    expect(names(sortItems(entries, "name"))).toEqual(["Deal", "gone", "Pricey"]);
  });

  it("filters deals and what needs attention", () => {
    expect(entries.filter((entry) => matches(entry.summary, "deals")).map((entry) => entry.item.name)).toEqual(["Deal"]);
    expect(entries.filter((entry) => matches(entry.summary, "attention")).map((entry) => entry.item.name)).toEqual(["gone"]);
    expect(entries.filter((entry) => matches(entry.summary, "all"))).toHaveLength(3);
  });
});

describe("targets", () => {
  it("shows how close the price is", () => {
    const close = item({ target_price: 1000 }, [{ last_price: 1040 }]);
    expect(targetProgress(close, summarize(close))).toEqual({ gap: 40, close: true, progress: 1000 / 1040 });
    const far = item({ target_price: 500 }, [{ last_price: 1000 }]);
    expect(targetProgress(far, summarize(far))?.close).toBe(false);
    const hit = item({ target_price: 1200 }, [{ last_price: 1000 }]);
    expect(targetProgress(hit, summarize(hit))).toEqual({ gap: -200, close: false, progress: 1 });
    expect(targetProgress(item(), summarize(item()))).toBeNull();
  });

  it("suggests the lowest price seen and 10% off", () => {
    expect(targetSuggestions(summarize(item({}, [{ last_price: 1299, stats: stats({ lowest_price: 1199 }) }])))).toEqual([
      { label: "Lowest seen", price: 1199 },
      { label: "10% off", price: 1160 },
    ]);
    expect(targetSuggestions(summarize(item({}, [{ last_price: null, last_in_stock: false }])))).toEqual([]);
  });
});
