import type { Item } from "../../lib/api";
import { storeName, timeAgo } from "../../lib/format";
import type { ItemSummary } from "../../lib/insights";
import { CartIcon, WarningIcon } from "../common/Icons";
import { Price, ProductImage, Sparkline, StoreChip, VibeBadge } from "../common/Product";
import { Movement, TargetLine } from "./PriceStatus";

interface Props {
  item: Item;
  summary: ItemSummary;
  onOpen: (itemId: number) => void;
}

/** One tracked item in the grid, like a product tile on a store's search page. */
export function ItemCard({ item, summary, onOpen }: Props) {
  const { best, price } = summary;
  const nameId = `item-${item.id}-name`;
  const open = () => onOpen(item.id);
  const failedCheck = item.listings.some((listing) => listing.last_error);

  return (
    <article className={`item-card vibe-${summary.vibe}`} aria-labelledby={nameId}>
      {/* The photo opens the details too; keyboards and screen readers use the name's button. */}
      <div className="item-card-media" onClick={open} aria-hidden="true">
        <ProductImage src={summary.image} />
        <VibeBadge vibe={summary.vibe} className="on-image" />
      </div>

      <div className="item-card-body">
        <div className="store-chips">
          {item.listings.map((listing) => (
            <StoreChip key={listing.id} site={listing.site} />
          ))}
          {!item.active && <span className="chip-muted">Paused</span>}
        </div>

        <h3 id={nameId} className="item-name">
          <button type="button" className="item-name-button" onClick={open} title={item.name}>
            {item.name}
          </button>
        </h3>

        <div className="price-row">
          {price !== null ? <Price amount={price} /> : <span className="out-of-stock">Out of stock</span>}
          {best && item.listings.length > 1 && <span className="muted small">on {storeName(best.site)}</span>}
        </div>
        <Movement summary={summary} />
        <TargetLine item={item} summary={summary} />

        {best?.stats && <Sparkline points={best.stats.recent_prices} />}

        {failedCheck && (
          <p className="card-warning">
            <WarningIcon size={14} /> A store check failed. See details.
          </p>
        )}

        <div className="item-card-foot">
          <span className="checked">{summary.lastChecked ? `Checked ${timeAgo(summary.lastChecked)}` : "Not checked yet"}</span>
          <div className="foot-actions">
            <button type="button" className="btn btn-small" onClick={open}>
              Details
            </button>
            {best && (
              <a className={`btn btn-small btn-store site-${best.site}`} href={best.url} target="_blank" rel="noopener noreferrer">
                <CartIcon size={14} /> Buy <span className="sr-only">{item.name}</span> on {storeName(best.site)}
              </a>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
