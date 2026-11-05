// Small pieces that show a product: its photo, its price the way Amazon writes
// it, which store it's on, its "vibe" and a tiny chart of its recent prices.

import { useState } from "react";

import type { PricePoint } from "../../lib/api";
import { formatRupees, priceParts, storeName } from "../../lib/format";
import { VIBES, type Vibe } from "../../lib/insights";

/** The store's photo of a product, or a placeholder when there's none or it won't load. */
export function ProductImage({ src, size = "card" }: { src: string | null; size?: "card" | "thumb" | "large" }) {
  const [broken, setBroken] = useState<string | null>(null);
  if (!src || broken === src) {
    return (
      <div className={`product-image placeholder ${size}`} aria-hidden="true">
        <span>🛍️</span>
      </div>
    );
  }
  return (
    <div className={`product-image ${size}`}>
      {/* No referrer: the store's image server doesn't need to know where it's shown. */}
      <img src={src} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(src)} />
    </div>
  );
}

/** ₹1,299 with a small ₹ and paise, as on Amazon. Screen readers hear "₹1,299.50". */
export function Price({ amount, size = "md" }: { amount: number; size?: "sm" | "md" | "lg" }) {
  const { whole, paise } = priceParts(amount);
  return (
    <span className={`price price-${size}`}>
      <span className="sr-only">{formatRupees(amount)}</span>
      <span className="price-symbol" aria-hidden="true">
        ₹
      </span>
      <span className="price-whole" aria-hidden="true">
        {whole}
      </span>
      {paise && (
        <span className="price-fraction" aria-hidden="true">
          {paise}
        </span>
      )}
    </span>
  );
}

export function StoreChip({ site }: { site: string }) {
  return <span className={`store-chip site-${site}`}>{storeName(site)}</span>;
}

export function VibeBadge({ vibe, className = "" }: { vibe: Vibe; className?: string }) {
  const { emoji, label, tone, hint } = VIBES[vibe];
  return (
    <span className={`vibe tone-${tone} ${className}`} title={hint}>
      <span aria-hidden="true">{emoji}</span> {label}
    </span>
  );
}

/** A tiny line of a store page's last 30 days, green when it went down, red when up. Decorative. */
export function Sparkline({ points }: { points: PricePoint[] }) {
  const priced = points.flatMap((point) =>
    point.in_stock && point.price !== null ? [{ t: Date.parse(point.checked_at), price: point.price }] : [],
  );
  if (priced.length < 2) return <div className="sparkline sparkline-empty" aria-hidden="true" />;

  const [width, height, pad] = [100, 28, 3];
  const [t0, t1] = [priced[0].t, priced[priced.length - 1].t];
  const prices = priced.map((point) => point.price);
  const [low, high] = [Math.min(...prices), Math.max(...prices)];
  const x = (t: number) => (t1 === t0 ? width / 2 : ((t - t0) / (t1 - t0)) * width);
  const y = (price: number) => (high === low ? height / 2 : pad + ((high - price) / (high - low)) * (height - 2 * pad));
  const path = priced.map((point, i) => `${i ? "L" : "M"}${x(point.t).toFixed(1)},${y(point.price).toFixed(1)}`).join("");
  const first = prices[0];
  const last = prices[prices.length - 1];
  const trend = last < first ? "down" : last > first ? "up" : "flat";

  return (
    <svg className={`sparkline trend-${trend}`} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <path d={`${path}L${width},${height}L0,${height}Z`} className="sparkline-area" />
      <path d={path} className="sparkline-line" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
