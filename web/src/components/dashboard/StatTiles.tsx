import { formatRupees, plural } from "../../lib/format";
import type { Filter, Totals } from "../../lib/insights";

interface Props {
  totals: Totals;
  onFilter: (filter: Filter) => void;
}

/** Four numbers that matter, each a shortcut to the items behind it. */
export function StatTiles({ totals, onFilter }: Props) {
  return (
    <section className="stat-tiles" aria-label="Summary">
      <Tile emoji="📦" label="Tracking" value={String(totals.items)} note={plural(totals.pages, "store page")} onClick={() => onFilter("all")} />
      <Tile
        emoji="🎯"
        label="Target hit"
        value={String(totals.targetHit)}
        note={totals.targetHit ? "Time to buy?" : "Not yet"}
        tone={totals.targetHit ? "great" : undefined}
        onClick={() => onFilter("target")}
      />
      <Tile
        emoji="📉"
        label="Price drops"
        value={String(totals.dropped)}
        note="since their last check"
        tone={totals.dropped ? "good" : undefined}
        onClick={() => onFilter("dropped")}
      />
      <Tile
        emoji="💸"
        label="Could save"
        value={formatRupees(totals.couldSave)}
        note="vs. their usual prices"
        tone={totals.couldSave ? "good" : undefined}
        onClick={() => onFilter("deals")}
      />
    </section>
  );
}

interface TileProps {
  emoji: string;
  label: string;
  value: string;
  note: string;
  tone?: "great" | "good";
  onClick: () => void;
}

function Tile({ emoji, label, value, note, tone, onClick }: TileProps) {
  return (
    <button type="button" className={`stat-tile ${tone ? `tone-${tone}` : ""}`} onClick={onClick}>
      <span className="stat-emoji" aria-hidden="true">
        {emoji}
      </span>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      <span className="stat-note">{note}</span>
    </button>
  );
}
