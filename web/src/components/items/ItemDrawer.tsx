import { useRef, useState } from "react";

import { useModal } from "../../hooks/useModal";
import { api, errorMessage, type CheckResult, type Item } from "../../lib/api";
import { formatRupees, missingStores, plural, storeName, timeAgo } from "../../lib/format";
import { canBuy, targetSuggestions, type ItemSummary } from "../../lib/insights";
import { CartIcon, CloseIcon, RefreshIcon, Spinner, TrashIcon, WarningIcon } from "../common/Icons";
import { Price, ProductImage, StoreChip, VibeBadge } from "../common/Product";
import type { Notice } from "../layout/Toast";
import { LinkForm, TargetForm } from "./ItemForms";
import { PriceHistory } from "./PriceHistory";
import { Movement, TargetLine } from "./PriceStatus";

interface Props {
  item: Item;
  summary: ItemSummary;
  onClose: () => void;
  onChange: (item: Item) => void;
  onRemove: (itemId: number) => void;
  onChecked: (result: CheckResult, done: string) => void;
  notify: (notice: Notice) => void;
}

type Busy = "check" | "target" | "link" | "remove" | null;

/** Everything about one item, in a panel over the dashboard: prices, history, target, stores. */
export function ItemDrawer({ item, summary, onClose, onChange, onRemove, onChecked, notify }: Props) {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const otherStores = missingStores(item.listings.map((listing) => listing.site));
  const titleId = `drawer-${item.id}-title`;

  useModal(panelRef, closeRef, onClose);

  async function run(kind: Exclude<Busy, null>, action: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(null);
    }
  }

  const checkNow = () => run("check", async () => onChecked(await api.checkItem(item.id), "Prices checked."));

  const saveTarget = (price: number | null) =>
    run("target", async () => {
      onChange(await api.setTarget(item.id, price));
      notify({ kind: "success", text: price === null ? "Target removed." : `Target set to ${formatRupees(price)} 🎯` });
    });

  const addLink = (link: string) =>
    run("link", async () => {
      const result = await api.addListing(item.id, link);
      const added = result.item.listings.at(-1);
      onChecked(result, added ? `Added ${storeName(added.site)}.` : "Added.");
    });

  const remove = () =>
    run("remove", async () => {
      await api.removeItem(item.id);
      onRemove(item.id);
      notify({ kind: "success", text: `Stopped tracking ${item.name}.` });
    });

  const suggestions = targetSuggestions(summary);

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside ref={panelRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="drawer-head">
          <ProductImage src={summary.image} size="large" />
          <div className="drawer-title">
            <div className="store-chips">
              {item.listings.map((listing) => (
                <StoreChip key={listing.id} site={listing.site} />
              ))}
              <VibeBadge vibe={summary.vibe} />
            </div>
            <h2 id={titleId}>{item.name}</h2>
            <div className="price-row">
              {summary.price !== null ? <Price amount={summary.price} size="lg" /> : <span className="out-of-stock">Out of stock everywhere</span>}
            </div>
            <Movement summary={summary} />
          </div>
          <button ref={closeRef} type="button" className="icon-button drawer-close" onClick={onClose} aria-label="Close details">
            <CloseIcon size={20} />
          </button>
        </header>

        <div className="drawer-body">
          {error && (
            <p className="message error" role="alert">
              <WarningIcon /> {error}
            </p>
          )}

          <section aria-labelledby={`${titleId}-stores`}>
            <h3 id={`${titleId}-stores`} className="drawer-section-title">
              Stores
            </h3>
            <ul className="store-list">
              {item.listings.map((listing) => (
                <li key={listing.id} className={summary.best?.id === listing.id && item.listings.length > 1 ? "cheapest" : undefined}>
                  <StoreChip site={listing.site} />
                  <span className="store-price">
                    {canBuy(listing) ? <Price amount={listing.last_price!} size="sm" /> : <span className="muted">Out of stock</span>}
                  </span>
                  {summary.best?.id === listing.id && item.listings.length > 1 && <span className="badge good">Cheapest</span>}
                  <span className="muted small push-right">
                    {listing.last_checked_at ? `Checked ${timeAgo(listing.last_checked_at)}` : "Not checked yet"}
                  </span>
                  <a className={`btn btn-small btn-store site-${listing.site}`} href={listing.url} target="_blank" rel="noopener noreferrer">
                    <CartIcon size={14} /> Open {storeName(listing.site)}
                  </a>
                  {listing.last_error && (
                    <p className="listing-error">
                      <WarningIcon size={14} /> Last check failed: {listing.last_error}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="stat-strip" aria-label="Price facts">
            <Fact label="🏆 Lowest seen" value={summary.lowest} />
            <Fact label="📊 Usual (30 days)" value={summary.usual} />
            <Fact label="📈 Highest seen" value={summary.highest} />
            <div className="fact">
              <span className="fact-label">🔁 Checks</span>
              <span className="fact-value">{summary.best?.stats?.checks ?? 0}</span>
            </div>
          </section>

          <PriceHistory item={item} />

          <section className="drawer-section" aria-labelledby={`${titleId}-target`}>
            <h3 id={`${titleId}-target`} className="drawer-section-title">
              Your target
            </h3>
            <TargetLine item={item} summary={summary} setHint="set one below to get an alert" />
            <TargetForm
              key={item.target_price ?? "none"}
              target={item.target_price}
              suggestions={suggestions}
              busy={busy === "target"}
              onSave={saveTarget}
            />
          </section>

          {otherStores.length > 0 && (
            <section className="drawer-section" aria-labelledby={`${titleId}-compare`}>
              <h3 id={`${titleId}-compare`} className="drawer-section-title">
                Compare stores
              </h3>
              <LinkForm stores={otherStores} busy={busy === "link"} onAdd={addLink} />
            </section>
          )}
        </div>

        <footer className="drawer-foot">
          {confirmRemove ? (
            <div className="confirm" role="group" aria-label="Confirm removal">
              <span>Stop tracking it? Its price history and alerts go too.</span>
              <button type="button" className="btn btn-danger" onClick={remove} disabled={busy !== null}>
                {busy === "remove" ? <Spinner /> : <TrashIcon />} Yes, remove
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmRemove(false)}>
                Keep it
              </button>
            </div>
          ) : (
            <>
              <button type="button" className="btn btn-yellow" onClick={checkNow} disabled={busy !== null}>
                {busy === "check" ? <Spinner /> : <RefreshIcon />}
                {busy === "check" ? `Checking ${plural(item.listings.length, "store")}…` : "Check now"}
              </button>
              <button type="button" className="btn btn-ghost danger push-right" onClick={() => setConfirmRemove(true)}>
                <TrashIcon /> Remove
              </button>
            </>
          )}
        </footer>
      </aside>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="fact">
      <span className="fact-label">{label}</span>
      <span className="fact-value">{value === null ? "—" : formatRupees(value)}</span>
    </div>
  );
}

