import { useCallback, useEffect, useState } from "react";

import { api, errorMessage, type Alert, type CheckResult, type Item } from "./api";
import { AddItemForm } from "./components/AddItemForm";
import { AlertsPanel } from "./components/AlertsPanel";
import { LogoIcon, WarningIcon } from "./components/Icons";
import { bestListing, ItemCard, type Notice } from "./components/ItemCard";
import { Toast } from "./components/Toast";
import { formatRupees, storeName } from "./format";

export default function App() {
  const [items, setItems] = useState<Item[] | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const closeNotice = useCallback(() => setNotice(null), []);

  const refresh = useCallback(async () => {
    try {
      const [freshItems, freshAlerts] = await Promise.all([api.listItems(), api.recentAlerts()]);
      setItems(freshItems);
      setAlerts(freshAlerts);
      setLoadError(null);
    } catch (failure) {
      setLoadError(errorMessage(failure));
    }
  }, []);

  // Load now, and again whenever you come back to the tab: the daily checks may have run.
  useEffect(() => {
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  function putItem(item: Item) {
    setItems((current) => {
      const list = current ?? [];
      return list.some((one) => one.id === item.id)
        ? list.map((one) => (one.id === item.id ? item : one))
        : [...list, item];
    });
  }

  /** Show what adding or checking found, and pick up any new alerts. */
  function showResult(result: CheckResult, done: string) {
    putItem(result.item);
    if (result.alerts.length) {
      setNotice({ kind: "alert", text: result.alerts.join(" · ") });
      api.recentAlerts().then(setAlerts, () => {});
    } else if (result.errors.length) {
      const failed = result.errors.map((problem) => `${storeName(problem.site)}: ${problem.error}`).join(" ");
      setNotice({ kind: "error", text: `${done} Some stores couldn't be checked. ${failed}` });
    } else {
      const best = bestListing(result.item);
      const price = best ? ` ${formatRupees(best.last_price!)} on ${storeName(best.site)}.` : " It's out of stock right now.";
      setNotice({ kind: "success", text: `${done}${price}` });
    }
  }

  const reached = items?.filter((item) => {
    const best = bestListing(item);
    return item.target_price !== null && best !== null && best.last_price! <= item.target_price;
  }).length;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <span className="logo">
            <LogoIcon size={20} />
          </span>
          <div>
            <h1>Price Tracker</h1>
            <p className="tagline">Amazon.in and Flipkart prices, checked twice a day. Drops go to your Telegram.</p>
          </div>
        </div>
      </header>

      <main className="layout">
        <div className="main-column">
          {loadError && (
            <div className="banner" role="alert">
              <WarningIcon />
              <span>{loadError}</span>
              <button type="button" className="button" onClick={() => void refresh()}>
                Try again
              </button>
            </div>
          )}

          <AddItemForm onAdded={(result) => showResult(result, `Now tracking ${result.item.name}.`)} />

          <section aria-labelledby="items-heading" className="items-section">
            <div className="section-head">
              <h2 id="items-heading">Your items</h2>
              {items && items.length > 0 && (
                <span className="muted">
                  {items.length} {items.length === 1 ? "item" : "items"}
                  {reached ? ` · ${reached} at or below target` : ""}
                </span>
              )}
            </div>

            {items === null ? (
              !loadError && <p className="muted">Loading your items…</p>
            ) : items.length === 0 ? (
              <EmptyState />
            ) : (
              <ul className="items">
                {items.map((item) => (
                  <li key={item.id}>
                    <ItemCard
                      item={item}
                      onChange={putItem}
                      onRemove={(id) => setItems((current) => current?.filter((one) => one.id !== id) ?? null)}
                      onChecked={showResult}
                      notify={setNotice}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="side-column">
          <AlertsPanel alerts={alerts} />
        </aside>
      </main>

      <Toast notice={notice} onClose={closeNotice} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card empty">
      <h3>Nothing tracked yet</h3>
      <ol>
        <li>
          In the Amazon or Flipkart app, open a product and tap <strong>Share</strong>, then <strong>Copy</strong>.
        </li>
        <li>Paste it in the box above. Add the price you'd like to pay, if you have one in mind.</li>
        <li>Prices are checked twice a day. You'll get a Telegram message when it's a good time to buy.</li>
      </ol>
    </div>
  );
}
