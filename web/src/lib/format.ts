// Writing prices, times and stores for people, the Indian way: ₹1,29,999.

const wholeRupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
const rupeesAndPaise = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const compactRupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** ₹1,299 for whole rupees, ₹470.50 otherwise, like the Telegram alerts. */
export function formatRupees(amount: number): string {
  return Number.isInteger(amount) ? wholeRupees.format(amount) : rupeesAndPaise.format(amount);
}

/** For chart axes: in full under ₹10,000, then compact (₹12K, ₹1.5L). */
export function formatAxisRupees(amount: number): string {
  return Math.abs(amount) >= 10_000 ? compactRupees.format(amount) : wholeRupees.format(amount);
}

const grouped = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** A price in the parts Amazon shows it in: ₹ 1,299 and a small .50, or no paise when there are none. */
export function priceParts(amount: number): { whole: string; paise: string | null } {
  const totalPaise = Math.round(amount * 100);
  const paise = totalPaise % 100;
  return { whole: grouped.format(Math.floor(totalPaise / 100)), paise: paise ? String(paise).padStart(2, "0") : null };
}

/** "12%", or "<1%" for a sliver. */
export function formatPercent(percent: number): string {
  const size = Math.abs(percent);
  return size > 0 && size < 1 ? "<1%" : `${Math.round(size)}%`;
}

/** "1 item", "3 items". */
export const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "just now", "5 minutes ago", "3 hours ago", "yesterday", then the date. */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const elapsed = now - new Date(iso).getTime();
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return relative.format(-Math.round(elapsed / MINUTE), "minute");
  if (elapsed < DAY) return relative.format(-Math.round(elapsed / HOUR), "hour");
  if (elapsed < 7 * DAY) return relative.format(-Math.round(elapsed / DAY), "day");
  return formatDate(iso);
}

/** "in 5 minutes", "in 3 hours", "tomorrow"; "any minute now" once it's due. */
export function timeUntil(iso: string, now: number = Date.now()): string {
  const left = new Date(iso).getTime() - now;
  if (left < MINUTE) return "any minute now";
  if (left < HOUR) return relative.format(Math.round(left / MINUTE), "minute");
  if (left < DAY) return relative.format(Math.round(left / HOUR), "hour");
  return relative.format(Math.round(left / DAY), "day");
}

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const timeFormat = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });
const dateTimeFormat = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

export const formatDate = (when: string | number) => dateFormat.format(new Date(when));
export const formatTime = (when: string | number) => timeFormat.format(new Date(when));
export const formatDateTime = (when: string | number) => dateTimeFormat.format(new Date(when));

const STORES: Record<string, string> = { amazon: "Amazon", flipkart: "Flipkart" };

export function storeName(site: string): string {
  return STORES[site] ?? site.charAt(0).toUpperCase() + site.slice(1);
}

/** The stores you can add a link for, other than the ones the item has. */
export function missingStores(sites: string[]): string[] {
  return Object.keys(STORES).filter((site) => !sites.includes(site));
}

/** Read a price someone typed: "1500", "1,499.50", "₹60,000". null when empty; NaN when not a price. */
export function parsePrice(text: string): number | null {
  const cleaned = text.trim().replace(/^(₹|rs\.?)\s*/i, "").replace(/,/g, "");
  if (!cleaned) return null;
  return /^\d+(\.\d{1,2})?$/.test(cleaned) && Number(cleaned) > 0 ? Number(cleaned) : Number.NaN;
}
