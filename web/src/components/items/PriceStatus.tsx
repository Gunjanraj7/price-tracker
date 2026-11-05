// How an item's price is doing, in words: against its usual price and the
// last check, and against your target. Used on the cards and in the details.

import type { Item } from "../../lib/api";
import { formatPercent, formatRupees } from "../../lib/format";
import { targetProgress, type ItemSummary } from "../../lib/insights";

/** "15% below usual" and "▼ ₹200 since last check", in green; red when it went the other way. */
export function Movement({ summary }: { summary: ItemSummary }) {
  const { usual, belowUsual, change } = summary;
  const parts = [];
  if (usual !== null && belowUsual !== null && Math.abs(belowUsual) >= 1) {
    const cheaper = belowUsual > 0;
    parts.push(
      <span key="usual" className={cheaper ? "good-text" : "bad-text"}>
        {formatPercent(belowUsual)} {cheaper ? "below" : "above"} usual{" "}
        <span className="muted">({formatRupees(usual)})</span>
      </span>,
    );
  }
  if (change !== null && change !== 0) {
    parts.push(
      <span key="change" className={change < 0 ? "good-text" : "bad-text"}>
        {change < 0 ? "▼" : "▲"} {formatRupees(Math.abs(change))} since last check
      </span>,
    );
  }
  return parts.length ? <p className="movement">{parts}</p> : null;
}

interface TargetLineProps {
  item: Item;
  summary: ItemSummary;
  /** What to say when there's no target yet, after "No target yet:". */
  setHint?: string;
}

/** How the price stands against the target, with a bar that fills as it gets closer. */
export function TargetLine({ item, summary, setHint = "set one in Details" }: TargetLineProps) {
  if (item.target_price === null) {
    return <p className="target-line muted">🎯 No target yet: {setHint}</p>;
  }
  const progress = targetProgress(item, summary);
  if (progress === null) {
    return <p className="target-line">🎯 Target {formatRupees(item.target_price)}</p>;
  }
  if (progress.gap <= 0) {
    return <p className="target-line target-hit">🎉 Target hit! {formatRupees(item.target_price)} or less</p>;
  }
  return (
    <div className="target-line">
      <div className="target-text">
        <span>
          🎯 {formatRupees(progress.gap)} to go {progress.close && <strong className="almost">· almost there!</strong>}
        </span>
        <span className="muted">target {formatRupees(item.target_price)}</span>
      </div>
      <div
        className="target-bar"
        role="progressbar"
        aria-label="How close to the target"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress.progress * 100)}
      >
        <span style={{ width: `${progress.progress * 100}%` }} />
      </div>
    </div>
  );
}
