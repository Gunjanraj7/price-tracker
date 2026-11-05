// The maths behind the price chart: turning the API's history into lines,
// round axis numbers, and step-shaped paths. Prices hold until the next check,
// so lines step rather than slope, and break where the product couldn't be bought.

import type { ListingHistory } from "./api";
import { formatDate, formatDateTime, formatTime, storeName } from "./format";

export interface Series {
  site: string;
  label: string;
  /** Every check, oldest first. price is null when it couldn't be bought. */
  points: { t: number; price: number | null }[];
}

export function toSeries(history: ListingHistory[]): Series[] {
  return history.map((listing) => ({
    site: listing.site,
    label: storeName(listing.site),
    points: listing.prices.map((point) => ({
      t: Date.parse(point.checked_at),
      price: point.in_stock ? point.price : null,
    })),
  }));
}

/** The price a series showed at time t: its last check at or before t. */
export function priceAt(series: Series, t: number): Series["points"][number] | undefined {
  let found: Series["points"][number] | undefined;
  for (const point of series.points) {
    if (point.t > t) break;
    found = point;
  }
  return found;
}

/** An SVG path that holds each price until the next check, with gaps where it couldn't be bought. */
export function stepPath(points: Series["points"], x: (t: number) => number, y: (price: number) => number): string {
  let path = "";
  let drawing = false;
  for (const point of points) {
    if (point.price === null) {
      if (drawing) path += `H${x(point.t).toFixed(1)}`;   // the price held until this check
      drawing = false;
    } else if (!drawing) {
      path += `M${x(point.t).toFixed(1)},${y(point.price).toFixed(1)}`;
      drawing = true;
    } else {
      path += `H${x(point.t).toFixed(1)}V${y(point.price).toFixed(1)}`;
    }
  }
  return path;
}

/** Round tick values just covering min..max: the smallest round step that needs at most `intervals` gaps. */
export function niceTicks(min: number, max: number, intervals = 5): number[] {
  if (min === max) {
    const pad = Math.max(10, min * 0.05);
    [min, max] = [Math.max(0, min - pad), max + pad];
  }
  const magnitude = 10 ** Math.floor(Math.log10((max - min) / intervals));
  for (const multiple of [1, 2, 2.5, 5, 10, 20]) {
    const step = multiple * magnitude;
    const [low, high] = [Math.floor(min / step), Math.ceil(max / step)];
    if (high - low <= intervals) {
      return Array.from({ length: high - low + 1 }, (_, i) => Math.round((low + i) * step * 100) / 100);
    }
  }
  return [min, max];
}

/** Dates (or times, for a day or two) along the bottom, about one per 100 pixels. */
export function timeTicks(t0: number, t1: number, plotWidth: number): { t: number; label: string }[] {
  if (t0 === t1) return [{ t: t0, label: formatDateTime(t0) }];
  const count = Math.max(2, Math.min(6, Math.floor(plotWidth / 100)));
  const format = t1 - t0 <= 2 * 24 * 3600_000 ? formatTime : formatDate;
  const ticks = Array.from({ length: count }, (_, i) => {
    const t = t0 + (i * (t1 - t0)) / (count - 1);
    return { t, label: format(t) };
  });
  return ticks.filter((tick, i) => i === 0 || tick.label !== ticks[i - 1].label);
}
