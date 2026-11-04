import { useId, useState } from "react";

import { api, errorMessage, type CheckResult, type Item, type Listing } from "../api";
import { formatRupees, missingStores, parsePrice, storeName, timeAgo } from "../format";
import {
  ChartIcon,
  CheckIcon,
  ExternalIcon,
  PlusIcon,
  RefreshIcon,
  Spinner,
  TargetIcon,
  TrashIcon,
  WarningIcon,
} from "./Icons";
import { PriceHistory } from "./PriceHistory";

export type Notice = { kind: "success" | "error" | "alert"; text: string };

interface Props {
  item: Item;
  onChange: (item: Item) => void;
  onRemove: (itemId: number) => void;
  onChecked: (result: CheckResult, done: string) => void;
  notify: (notice: Notice) => void;
}

type Panel = "none" | "target" | "link" | "remove";
type Busy = "check" | "target" | "link" | "remove" | null;

const canBuy = (listing: Listing) => listing.last_in_stock === true && listing.last_price !== null;

/** The listing with the lowest price you can buy at now, if any. */
export function bestListing(item: Item): Listing | null {
  return item.listings.filter(canBuy).reduce<Listing | null>(
    (best, listing) => (best === null || listing.last_price! < best.last_price! ? listing : best),
    null,
  );
}

export function ItemCard({ item, onChange, onRemove, onChecked, notify }: Props) {
  const [panel, setPanel] = useState<Panel>("none");
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const historyId = useId();
  const best = bestListing(item);
  const comparable = item.listings.filter(canBuy).length > 1;
  const otherStores = missingStores(item.listings.map((listing) => listing.site));

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

  const checkNow = () =>
    run("check", async () => {
      onChecked(await api.checkItem(item.id), "Prices checked.");
    });

  const saveTarget = (price: number | null) =>
    run("target", async () => {
      onChange(await api.setTarget(item.id, price));
      setPanel("none");
      notify({ kind: "success", text: price === null ? "Target removed." : `Target set to ${formatRupees(price)}.` });
    });

  const addLink = (link: string) =>
    run("link", async () => {
      const result = await api.addListing(item.id, link);
      setPanel("none");
      const added = result.item.listings.at(-1);
      onChecked(result, added ? `Added ${storeName(added.site)}.` : "Added.");
    });

  const remove = () =>
    run("remove", async () => {
      await api.removeItem(item.id);
      onRemove(item.id);
      notify({ kind: "success", text: `Stopped tracking ${item.name}.` });
    });

  const toggle = (next: Panel) => {
    setError(null);
    setPanel((current) => (current === next ? "none" : next));
  };

  return (
    <article className="card item" aria-labelledby={`item-${item.id}-name`}>
      <header className="item-head">
        <h3 id={`item-${item.id}-name`} className="item-name" title={item.name}>
          {item.name}
        </h3>
        {!item.active && <span className="badge">Paused</span>}
      </header>

      <ul className="listings">
        {item.listings.map((listing) => (
          <li key={listing.id} className={`listing site-${listing.site}`}>
            <span className="store">
              <span className="store-dot" aria-hidden="true" />
              {storeName(listing.site)}
            </span>
            <span className="price">
              {canBuy(listing) ? formatRupees(listing.last_price!) : <span className="muted">Out of stock</span>}
            </span>
            {comparable && best?.id === listing.id && <span className="badge good">Lowest</span>}
            <span className="checked">
              {listing.last_checked_at ? `Checked ${timeAgo(listing.last_checked_at)}` : "Not checked yet"}
            </span>
            <a className="open-link" href={listing.url} target="_blank" rel="noopener noreferrer">
              Open <span className="sr-only">on {storeName(listing.site)}</span>
              <ExternalIcon size={14} />
            </a>
            {listing.last_error && (
              <p className="listing-error">
                <WarningIcon size={14} /> Last check failed: {listing.last_error}
              </p>
            )}
          </li>
        ))}
      </ul>

      <TargetStatus item={item} best={best} />

      <div className="actions">
        <button type="button" className="button" onClick={checkNow} disabled={busy !== null}>
          {busy === "check" ? <Spinner /> : <RefreshIcon />}
          {busy === "check" ? "Checking…" : "Check now"}
        </button>
        <button
          type="button"
          className="button"
          aria-expanded={showHistory}
          aria-controls={historyId}
          onClick={() => setShowHistory((shown) => !shown)}
        >
          <ChartIcon />
          {showHistory ? "Hide history" : "Price history"}
        </button>
        <button type="button" className="button" aria-expanded={panel === "target"} onClick={() => toggle("target")}>
          <TargetIcon />
          {item.target_price === null ? "Set target" : "Change target"}
        </button>
        {otherStores.length > 0 && (
          <button type="button" className="button" aria-expanded={panel === "link"} onClick={() => toggle("link")}>
            <PlusIcon />
            Add {otherStores.map(storeName).join(" or ")} link
          </button>
        )}
        <button
          type="button"
          className="button ghost danger push-right"
          aria-expanded={panel === "remove"}
          onClick={() => toggle("remove")}
        >
          <TrashIcon />
          Remove
        </button>
      </div>

      {panel === "target" && (
        <TargetForm item={item} busy={busy === "target"} onSave={saveTarget} onCancel={() => setPanel("none")} />
      )}
      {panel === "link" && (
        <LinkForm stores={otherStores} busy={busy === "link"} onAdd={addLink} onCancel={() => setPanel("none")} />
      )}
      {panel === "remove" && (
        <div className="inline-panel confirm" role="group" aria-label="Confirm removal">
          <p>Stop tracking this item? Its price history and alerts are deleted too.</p>
          <button type="button" className="button danger-solid" onClick={remove} disabled={busy !== null}>
            {busy === "remove" ? <Spinner /> : <TrashIcon />} Yes, remove
          </button>
          <button type="button" className="button ghost" onClick={() => setPanel("none")}>
            Cancel
          </button>
        </div>
      )}

      {error && (
        <p className="message error" role="alert">
          <WarningIcon /> {error}
        </p>
      )}

      <div id={historyId} hidden={!showHistory}>
        {showHistory && <PriceHistory item={item} />}
      </div>
    </article>
  );
}

function TargetStatus({ item, best }: { item: Item; best: Listing | null }) {
  const target = item.target_price;
  if (target === null) {
    return <p className="target-status muted">No target yet. Set one to get an alert when the price gets close.</p>;
  }
  if (best === null) {
    return <p className="target-status">Your target: {formatRupees(target)}</p>;
  }
  const price = best.last_price!;
  if (price <= target) {
    return (
      <p className="target-status good">
        <CheckIcon /> At or below your {formatRupees(target)} target
      </p>
    );
  }
  const gap = Math.round((price - target) * 100) / 100;
  const close = (gap / target) * 100 <= 5;
  return (
    <p className="target-status">
      {formatRupees(gap)} above your {formatRupees(target)} target
      {close && <span className="badge">Within 5%</span>}
    </p>
  );
}

function TargetForm(props: { item: Item; busy: boolean; onSave: (price: number | null) => void; onCancel: () => void }) {
  const { item, busy, onSave, onCancel } = props;
  const [text, setText] = useState(item.target_price === null ? "" : String(item.target_price));
  const [problem, setProblem] = useState<string | null>(null);
  const inputId = useId();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const price = parsePrice(text);
    if (price === null || Number.isNaN(price)) {
      setProblem("Write the price you'd like to pay, like 1500 or 1,499.50.");
      return;
    }
    onSave(price);
  }

  return (
    <form className="inline-panel" onSubmit={submit} onKeyDown={(event) => event.key === "Escape" && onCancel()}>
      <label htmlFor={inputId}>Alert me when the price gets close to</label>
      <div className="inline-row">
        <div className="rupee-input">
          <span aria-hidden="true">₹</span>
          <input
            id={inputId}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            autoFocus
            value={text}
            onChange={(event) => setText(event.target.value)}
            disabled={busy}
            aria-invalid={problem ? true : undefined}
          />
        </div>
        <button type="submit" className="button primary" disabled={busy}>
          {busy && <Spinner />} Save
        </button>
        {item.target_price !== null && (
          <button type="button" className="button" onClick={() => onSave(null)} disabled={busy}>
            Remove target
          </button>
        )}
        <button type="button" className="button ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {problem && <p className="message error">{problem}</p>}
    </form>
  );
}

function LinkForm(props: { stores: string[]; busy: boolean; onAdd: (link: string) => void; onCancel: () => void }) {
  const { stores, busy, onAdd, onCancel } = props;
  const [link, setLink] = useState("");
  const inputId = useId();
  const names = stores.map(storeName).join(" or ");

  return (
    <form
      className="inline-panel"
      onSubmit={(event) => {
        event.preventDefault();
        if (link.trim()) onAdd(link.trim());
      }}
      onKeyDown={(event) => event.key === "Escape" && onCancel()}
    >
      <label htmlFor={inputId}>The same product on {names}</label>
      <div className="inline-row">
        <input
          id={inputId}
          type="text"
          inputMode="url"
          autoComplete="off"
          autoFocus
          placeholder={`Paste the ${names} link`}
          value={link}
          onChange={(event) => setLink(event.target.value)}
          disabled={busy}
          className="grow"
        />
        <button type="submit" className="button primary" disabled={busy || !link.trim()}>
          {busy ? <Spinner /> : <PlusIcon />} {busy ? "Getting the price…" : "Add"}
        </button>
        <button type="button" className="button ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
