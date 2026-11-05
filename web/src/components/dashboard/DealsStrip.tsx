import type { Item } from "../../lib/api";
import { formatPercent } from "../../lib/format";
import type { ItemSummary } from "../../lib/insights";
import { Price, ProductImage, VibeBadge } from "../common/Product";

interface Props {
  deals: { item: Item; summary: ItemSummary }[];
  onOpen: (itemId: number) => void;
}

/** The best deals right now, in a row like a store's "Deals of the day". Hidden when there are none. */
export function DealsStrip({ deals, onOpen }: Props) {
  if (!deals.length) return null;
  return (
    <section className="deals" aria-labelledby="deals-heading">
      <div className="deals-head">
        <h2 id="deals-heading">🔥 Hot right now</h2>
        <span className="muted small">Your best prices today</span>
      </div>
      <ul className="deals-row">
        {deals.map(({ item, summary }) => (
          <li key={item.id}>
            <button type="button" className="deal-card" onClick={() => onOpen(item.id)}>
              <ProductImage src={summary.image} size="thumb" />
              <span className="deal-name">{item.name}</span>
              {summary.price !== null && <Price amount={summary.price} size="sm" />}
              <span className="deal-why">{whyItsADeal(summary)}</span>
              <VibeBadge vibe={summary.vibe} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function whyItsADeal(summary: ItemSummary): string {
  if (summary.targetHit) return "🎯 At your target";
  if (summary.belowUsual !== null && summary.belowUsual >= 1) return `${formatPercent(summary.belowUsual)} below usual`;
  return "Lowest so far";
}
