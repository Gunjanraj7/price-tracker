import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { api, errorMessage, type Item, type ListingHistory } from "../../lib/api";
import { niceTicks, priceAt, stepPath, timeTicks, toSeries, type Series } from "../../lib/chart";
import { formatAxisRupees, formatDate, formatDateTime, formatRupees } from "../../lib/format";
import { WarningIcon } from "../common/Icons";

const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "1 year" },
];

/** An item's price history: range buttons, then a chart or a table of every check. */
export function PriceHistory({ item }: { item: Item }) {
  const [days, setDays] = useState(30);
  const [history, setHistory] = useState<ListingHistory[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);
  // Fetch again when the item has been checked since.
  const lastCheck = item.listings.map((listing) => listing.last_checked_at ?? "").sort().at(-1);

  useEffect(() => {
    let current = true;   // false once a newer request has replaced this one
    setLoading(true);
    api.priceHistory(item.id, days).then(
      (answer) => {
        if (!current) return;
        setHistory(answer);
        setError(null);
        setLoading(false);
      },
      (failure) => {
        if (!current) return;
        setError(errorMessage(failure));
        setLoading(false);
      },
    );
    return () => {
      current = false;
    };
  }, [item.id, days, lastCheck]);

  const series = useMemo(() => (history ? toSeries(history) : []), [history]);
  const priced = series.flatMap((one) =>
    one.points.flatMap((point) => (point.price === null ? [] : [{ ...point, label: one.label }])),
  );
  const lowest = priced.reduce<(typeof priced)[number] | null>(
    (best, point) => (best === null || point.price! < best.price! ? point : best),
    null,
  );

  return (
    <section className="history" aria-label={`Price history of ${item.name}`}>
      <div className="history-bar">
        <div className="segmented" role="group" aria-label="Time range">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              aria-pressed={days === range.days}
              onClick={() => setDays(range.days)}
            >
              {range.label}
            </button>
          ))}
        </div>
        <button type="button" className="link-button" onClick={() => setAsTable((table) => !table)}>
          {asTable ? "Show chart" : "Show as table"}
        </button>
      </div>

      {error && (
        <p className="message error" role="alert">
          <WarningIcon /> {error}
        </p>
      )}
      {history === null && !error && <p className="muted">Loading prices…</p>}

      {history !== null && (
        <div className={loading ? "refreshing" : undefined}>
          {series.length > 1 && !asTable && <Legend series={series} />}
          {series.length === 1 && !asTable && <p className="chart-title">{series[0].label} price</p>}
          {priced.length === 0 ? (
            <p className="muted empty-chart">
              {series.some((one) => one.points.length)
                ? "It was out of stock at every check in this period."
                : "No checks in this period yet. Prices are recorded at every check, twice a day."}
            </p>
          ) : asTable ? (
            <HistoryTable series={series} />
          ) : (
            <PriceChart series={series} target={item.target_price} />
          )}
          {lowest && (
            <p className="chart-summary">
              Lowest in this period: <strong>{formatRupees(lowest.price!)}</strong> on {lowest.label},{" "}
              {formatDate(lowest.t)}
              {priced.length === 1 && ". The chart fills in as more checks run."}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Legend({ series }: { series: Series[] }) {
  return (
    <ul className="legend" aria-label="Stores">
      {series.map((one) => (
        <li key={one.site}>
          <svg width="16" height="8" aria-hidden="true" className={`site-${one.site}`}>
            <line x1="1" y1="4" x2="15" y2="4" className="series-stroke" />
          </svg>
          {one.label}
        </li>
      ))}
    </ul>
  );
}

function HistoryTable({ series }: { series: Series[] }) {
  const rows = series
    .flatMap((one) => one.points.map((point) => ({ ...point, label: one.label })))
    .sort((a, b) => b.t - a.t);
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">Every price check, newest first</caption>
        <thead>
          <tr>
            <th scope="col">Checked</th>
            <th scope="col">Store</th>
            <th scope="col" className="num">
              Price
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              <td>{formatDateTime(row.t)}</td>
              <td>{row.label}</td>
              <td className="num">{row.price === null ? "Out of stock" : formatRupees(row.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// The chart. Its maths (ticks, step paths) is in lib/chart.ts.

const HEIGHT = 248;
const MARGIN = { top: 14, right: 84, bottom: 34, left: 64 };

export function PriceChart({ series, target }: { series: Series[]; target: number | null }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const width = useWidth(boxRef);
  const [active, setActive] = useState<number | null>(null);
  const summaryId = useId();

  const times = useMemo(
    () => [...new Set(series.flatMap((one) => one.points.map((point) => point.t)))].sort((a, b) => a - b),
    [series],
  );
  const prices = series.flatMap((one) => one.points.flatMap((point) => (point.price === null ? [] : [point.price])));
  if (!prices.length) return null;

  const ticks = niceTicks(Math.min(...prices, target ?? Infinity), Math.max(...prices, target ?? -Infinity));
  const [yMin, yMax] = [ticks[0], ticks[ticks.length - 1]];
  const margin = width < 440 ? { ...MARGIN, left: 52, right: 68 } : MARGIN;   // phones
  const left = margin.left;
  const right = width - margin.right;
  const top = margin.top;
  const bottom = HEIGHT - margin.bottom;
  const [t0, t1] = [times[0], times[times.length - 1]];
  const x = (t: number) => (t1 === t0 ? (left + right) / 2 : left + ((t - t0) / (t1 - t0)) * (right - left));
  const y = (price: number) => bottom - ((price - yMin) / (yMax - yMin)) * (bottom - top);

  const ends = series.flatMap((one) => {
    const last = one.points.at(-1);
    return last && last.price !== null ? [{ site: one.site, label: one.label, t: last.t, price: last.price }] : [];
  });
  // Label the line ends unless they'd sit on top of each other; the legend and tooltip cover that case.
  const labelEnds = ends.every((end, i) => ends.slice(i + 1).every((other) => Math.abs(y(end.price) - y(other.price)) >= 30));

  const activeTime = active === null ? null : times[active];
  const readings = activeTime === null ? [] : series.map((one) => ({ ...one, point: priceAt(one, activeTime) }));

  function pointAt(clientX: number) {
    const box = boxRef.current!.getBoundingClientRect();
    const px = clientX - box.left;
    let nearest = 0;
    times.forEach((t, i) => {
      if (Math.abs(x(t) - px) < Math.abs(x(times[nearest]) - px)) nearest = i;
    });
    setActive(nearest);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const last = times.length - 1;
    const moves: Record<string, number> = {
      ArrowLeft: Math.max(0, (active ?? last) - 1),
      ArrowRight: Math.min(last, (active ?? -1) + 1),
      Home: 0,
      End: last,
    };
    if (event.key in moves) {
      event.preventDefault();
      setActive(moves[event.key]);
    } else if (event.key === "Escape") {
      setActive(null);
    }
  }

  const summary = series
    .map((one) => {
      const own = one.points.flatMap((point) => (point.price === null ? [] : [point.price]));
      return own.length
        ? `${one.label}: latest ${formatRupees(own[own.length - 1])}, lowest ${formatRupees(Math.min(...own))}`
        : `${one.label}: out of stock`;
    })
    .join(". ");

  return (
    <div
      ref={boxRef}
      className="chart"
      tabIndex={0}
      role="group"
      aria-label="Price chart. Use the left and right arrow keys to read each check."
      aria-describedby={summaryId}
      onPointerMove={(event) => pointAt(event.clientX)}
      onPointerLeave={() => setActive(null)}
      onKeyDown={onKeyDown}
      onBlur={() => setActive(null)}
    >
      <p id={summaryId} className="sr-only">
        {summary}
      </p>
      <svg width={width} height={HEIGHT} aria-hidden="true">
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={left} x2={right} y1={y(tick)} y2={y(tick)} />
            <text className="axis-label" x={left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
              {formatAxisRupees(tick)}
            </text>
          </g>
        ))}
        <line className="baseline" x1={left} x2={right} y1={bottom} y2={bottom} />
        {timeTicks(t0, t1, right - left).map((tick, i, all) => (
          <text
            key={tick.t}
            className="axis-label"
            x={x(tick.t)}
            y={bottom + 20}
            textAnchor={all.length === 1 ? "middle" : i === 0 ? "start" : i === all.length - 1 ? "end" : "middle"}
          >
            {tick.label}
          </text>
        ))}

        {target !== null && (
          <g className="target">
            <line x1={left} x2={right} y1={y(target)} y2={y(target)} />
            <text x={left + 6} y={y(target) - 6 < top + 10 ? y(target) + 14 : y(target) - 6}>
              Your target {formatRupees(target)}
            </text>
          </g>
        )}

        {series.map((one) => (
          <path key={one.site} className={`price-line site-${one.site}`} d={stepPath(one.points, x, y)} />
        ))}

        {activeTime !== null && (
          <line className="crosshair" x1={x(activeTime)} x2={x(activeTime)} y1={top} y2={bottom} />
        )}

        {ends.map((end) => (
          <circle key={end.site} className={`dot site-${end.site}`} cx={x(end.t)} cy={y(end.price)} r={4} />
        ))}
        {readings.map(
          (reading) =>
            reading.point?.price != null && (
              <circle
                key={reading.site}
                className={`dot site-${reading.site}`}
                cx={x(activeTime!)}
                cy={y(reading.point.price)}
                r={5}
              />
            ),
        )}

        {labelEnds &&
          ends.map((end) => (
            <text key={end.site} className="end-label" x={right + 10} y={y(end.price)}>
              <tspan dy="-0.1em">{formatRupees(end.price)}</tspan>
              {series.length > 1 && (
                <tspan className="end-store" x={right + 10} dy="1.2em">
                  {end.label}
                </tspan>
              )}
            </text>
          ))}
      </svg>

      {activeTime !== null && (
        <div
          className="tooltip"
          style={
            x(activeTime) > width / 2
              ? { right: width - x(activeTime) + 12, top }
              : { left: x(activeTime) + 12, top }
          }
          aria-live="polite"
        >
          <div className="tooltip-time">{formatDateTime(activeTime)}</div>
          {readings.map((reading) => (
            <div key={reading.site} className="tooltip-row">
              {series.length > 1 && (
                <svg width="12" height="8" aria-hidden="true" className={`site-${reading.site}`}>
                  <line x1="1" y1="4" x2="11" y2="4" className="series-stroke" />
                </svg>
              )}
              <strong>
                {reading.point === undefined
                  ? "Not tracked yet"
                  : reading.point.price === null
                    ? "Out of stock"
                    : formatRupees(reading.point.price)}
              </strong>
              <span>{reading.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** The element's width, kept up to date as the window resizes. */
function useWidth(ref: React.RefObject<HTMLElement | null>, fallback = 640): number {
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = (measured: number) => measured > 0 && setWidth(Math.max(280, Math.round(measured)));
    update(element.getBoundingClientRect().width);   // before the first paint, so there's no jump
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => update(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
