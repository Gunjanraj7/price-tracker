// What the dashboard says about each item: its best price now, how that
// compares with its usual price and your target, and a one-glance "vibe".
// The usual price is the middle price of the last 30 days of checks, the same
// one the big-drop alert uses (see price_tracker/alerts.py).

import type { Item, Listing } from "./api";

export const canBuy = (listing: Listing) => listing.last_in_stock === true && listing.last_price !== null;

/** The listing with the lowest price you can buy at now, if any. */
export function bestListing(item: Item): Listing | null {
  return item.listings.filter(canBuy).reduce<Listing | null>(
    (best, listing) => (best === null || listing.last_price! < best.last_price! ? listing : best),
    null,
  );
}

export type Vibe = "target" | "lowest" | "hot" | "good" | "mid" | "pricey" | "new" | "out";
export type Tone = "win" | "great" | "good" | "neutral" | "bad" | "info";

/** This far below its usual price is a great deal. */
export const HOT_PERCENT = 10;
/** Within this of its usual price is a normal price. */
export const MID_PERCENT = 2;
/** The near-target alert's margin (config.NEAR_TARGET_PERCENT). */
export const NEAR_TARGET_PERCENT = 5;

export const VIBES: Record<Vibe, { emoji: string; label: string; tone: Tone; hint: string }> = {
  target: { emoji: "🎯", label: "Target hit", tone: "win", hint: "At or below your target price" },
  lowest: { emoji: "🏆", label: "Lowest ever", tone: "great", hint: "The lowest price since you started tracking it" },
  hot: { emoji: "🔥", label: "W deal", tone: "great", hint: `${HOT_PERCENT}% or more below its usual price` },
  good: { emoji: "👍", label: "Good price", tone: "good", hint: "A bit below its usual price" },
  mid: { emoji: "😐", label: "Mid price", tone: "neutral", hint: "About its usual price" },
  pricey: { emoji: "📈", label: "Pricey rn", tone: "bad", hint: "Above its usual price: maybe wait" },
  new: { emoji: "👀", label: "Just started", tone: "info", hint: "A few more checks and it gets a verdict" },
  out: { emoji: "🚫", label: "Out of stock", tone: "neutral", hint: "Not for sale on any store right now" },
};

/** The order "Best deals first" sorts by. */
const VIBE_RANK: Vibe[] = ["target", "lowest", "hot", "good", "mid", "new", "pricey", "out"];

export interface ItemSummary {
  best: Listing | null;
  /** The best price now, on any store; null when it can't be bought. */
  price: number | null;
  /** The best store's usual price. */
  usual: number | null;
  /** The lowest and highest prices seen on any store since tracking began. */
  lowest: number | null;
  highest: number | null;
  /** The best price minus the same store's price at the check before. Negative: it got cheaper. */
  change: number | null;
  /** How many percent below its usual price it is now. Negative: above it. */
  belowUsual: number | null;
  /** The best price minus the target. Zero or less: the target is hit. */
  targetGap: number | null;
  targetHit: boolean;
  vibe: Vibe;
  /** A check failed, or no store has it for sale. */
  needsAttention: boolean;
  /** The newest check of any of its store pages. */
  lastChecked: string | null;
  image: string | null;
}

const cents = (amount: number) => Math.round(amount * 100) / 100;

export function summarize(item: Item): ItemSummary {
  const best = bestListing(item);
  const price = best?.last_price ?? null;
  const stats = best?.stats ?? null;
  const usual = stats?.usual_price ?? null;
  const all = item.listings.flatMap((listing) => (listing.stats ? [listing.stats] : []));
  const lowests = all.flatMap((one) => (one.lowest_price === null ? [] : [one.lowest_price]));
  const highests = all.flatMap((one) => (one.highest_price === null ? [] : [one.highest_price]));
  const lowest = lowests.length ? Math.min(...lowests) : null;
  const highest = highests.length ? Math.max(...highests) : null;
  const previous = stats?.previous_price ?? null;

  const change = price !== null && previous !== null ? cents(price - previous) : null;
  const belowUsual = price !== null && usual ? ((usual - price) / usual) * 100 : null;
  const targetGap = price !== null && item.target_price !== null ? cents(price - item.target_price) : null;
  const targetHit = targetGap !== null && targetGap <= 0;
  const checks = stats?.checks ?? 0;

  let vibe: Vibe;
  if (price === null) vibe = "out";
  else if (targetHit) vibe = "target";
  else if (checks < 2 || belowUsual === null) vibe = "new";
  else if (lowest !== null && price <= lowest && checks >= 3 && belowUsual > 0) vibe = "lowest";
  else if (belowUsual >= HOT_PERCENT) vibe = "hot";
  else if (belowUsual > MID_PERCENT) vibe = "good";
  else if (belowUsual >= -MID_PERCENT) vibe = "mid";
  else vibe = "pricey";

  const checkTimes = item.listings.flatMap((listing) => (listing.last_checked_at ? [listing.last_checked_at] : []));
  return {
    best,
    price,
    usual,
    lowest,
    highest,
    change,
    belowUsual,
    targetGap,
    targetHit,
    vibe,
    needsAttention: item.listings.some((listing) => listing.last_error) || (item.listings.length > 0 && best === null),
    lastChecked: checkTimes.length ? checkTimes.reduce((newest, time) => (time > newest ? time : newest)) : null,
    image: best?.image_url ?? item.listings.find((listing) => listing.image_url)?.image_url ?? null,
  };
}

/** An item with its summary, as the dashboard lists them. */
export type ItemEntry = { item: Item; summary: ItemSummary };

export const isDeal = (summary: ItemSummary) => ["target", "lowest", "hot"].includes(summary.vibe);

export interface Totals {
  items: number;
  pages: number;
  targetHit: number;
  dropped: number;
  deals: number;
  attention: number;
  /** How much less than their usual prices the items cost now, added up. */
  couldSave: number;
}

export function totals(summaries: ItemEntry[]): Totals {
  return {
    items: summaries.length,
    pages: summaries.reduce((count, { item }) => count + item.listings.length, 0),
    targetHit: summaries.filter(({ summary }) => summary.targetHit).length,
    dropped: summaries.filter(({ summary }) => summary.change !== null && summary.change < 0).length,
    deals: summaries.filter(({ summary }) => isDeal(summary)).length,
    attention: summaries.filter(({ summary }) => summary.needsAttention).length,
    couldSave: cents(
      summaries.reduce(
        (sum, { summary }) =>
          summary.usual !== null && summary.price !== null ? sum + Math.max(0, summary.usual - summary.price) : sum,
        0,
      ),
    ),
  };
}

export type Filter = "all" | "target" | "dropped" | "deals" | "attention";

export const FILTERS: { value: Filter; label: string; emoji: string; empty: string }[] = [
  { value: "all", label: "All items", emoji: "🛍️", empty: "Nothing tracked yet." },
  { value: "target", label: "Target hit", emoji: "🎯", empty: "No target hits yet. Patience pays off 🧘" },
  { value: "dropped", label: "Price dropped", emoji: "📉", empty: "Nothing got cheaper since its last check." },
  { value: "deals", label: "Deals", emoji: "🔥", empty: "No hot deals right now. We'll keep watching 👀" },
  { value: "attention", label: "Needs attention", emoji: "⚠️", empty: "All good: every check worked ✨" },
];

export function matches(summary: ItemSummary, filter: Filter): boolean {
  switch (filter) {
    case "target":
      return summary.targetHit;
    case "dropped":
      return summary.change !== null && summary.change < 0;
    case "deals":
      return isDeal(summary);
    case "attention":
      return summary.needsAttention;
    default:
      return true;
  }
}

export type Sort = "deals" | "newest" | "price-low" | "price-high" | "name";

export const SORTS: { value: Sort; label: string }[] = [
  { value: "deals", label: "Best deals first" },
  { value: "newest", label: "Newest first" },
  { value: "price-low", label: "Price: low to high" },
  { value: "price-high", label: "Price: high to low" },
  { value: "name", label: "Name" },
];

export function sortItems(entries: ItemEntry[], sort: Sort): ItemEntry[] {
  const byPrice = (direction: 1 | -1) => (a: ItemEntry, b: ItemEntry) => {
    if (a.summary.price === null) return b.summary.price === null ? 0 : 1;   // out of stock last
    if (b.summary.price === null) return -1;
    return direction * (a.summary.price - b.summary.price);
  };
  const compare: Record<Sort, (a: ItemEntry, b: ItemEntry) => number> = {
    deals: (a, b) =>
      VIBE_RANK.indexOf(a.summary.vibe) - VIBE_RANK.indexOf(b.summary.vibe) ||
      (b.summary.belowUsual ?? -Infinity) - (a.summary.belowUsual ?? -Infinity) ||
      b.item.id - a.item.id,
    newest: (a, b) => b.item.created_at.localeCompare(a.item.created_at) || b.item.id - a.item.id,
    "price-low": byPrice(1),
    "price-high": byPrice(-1),
    name: (a, b) => a.item.name.localeCompare(b.item.name, "en", { sensitivity: "base" }),
  };
  return [...entries].sort(compare[sort]);
}

/** Targets worth one tap: the lowest price seen, and 10% off today's, when they're below today's price. */
export function targetSuggestions(summary: ItemSummary): { label: string; price: number }[] {
  const { price, lowest } = summary;
  if (price === null) return [];
  const found: { label: string; price: number }[] = [];
  if (lowest !== null && lowest < price) found.push({ label: "Lowest seen", price: lowest });
  const tenOff = Math.floor((price * 0.9) / 10) * 10;
  if (tenOff > 0 && tenOff < price && tenOff !== lowest) found.push({ label: "10% off", price: tenOff });
  return found;
}

/** How the target looks now: how far the best price is from it, and how close (0..1) for a progress bar. */
export function targetProgress(item: Item, summary: ItemSummary): { gap: number; close: boolean; progress: number } | null {
  if (item.target_price === null || summary.price === null || summary.targetGap === null) return null;
  const gap = summary.targetGap;
  return {
    gap,
    close: gap > 0 && (gap / item.target_price) * 100 <= NEAR_TARGET_PERCENT,
    progress: gap <= 0 ? 1 : Math.max(0.04, Math.min(1, item.target_price / summary.price)),
  };
}
