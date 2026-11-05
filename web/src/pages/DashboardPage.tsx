import { useCallback, useMemo, useState } from "react";

import { WarningIcon } from "../components/common/Icons";
import { AlertsPanel } from "../components/dashboard/AlertsPanel";
import { DealsStrip } from "../components/dashboard/DealsStrip";
import { FilterTabs } from "../components/dashboard/FilterTabs";
import { Greeting } from "../components/dashboard/Greeting";
import { ItemsSection } from "../components/dashboard/ItemsSection";
import { SchedulePanel, ScheduleStatus } from "../components/dashboard/Schedule";
import { StatTiles } from "../components/dashboard/StatTiles";
import { ItemDrawer } from "../components/items/ItemDrawer";
import { Header } from "../components/layout/Header";
import { Toast, type Notice } from "../components/layout/Toast";
import { describeCheckAll, useCheckAll } from "../hooks/useCheckAll";
import { useDashboardData } from "../hooks/useDashboardData";
import { api, type CheckResult } from "../lib/api";
import { confetti } from "../lib/confetti";
import { formatRupees, storeName } from "../lib/format";
import { bestListing, FILTERS, isDeal, matches, sortItems, summarize, totals, type Filter } from "../lib/insights";

interface Props {
  username: string;
  onLoggedOut: () => void;
}

/** The dashboard: everything you track, what's worth buying now, and the latest alerts. */
export function DashboardPage({ username, onLoggedOut }: Props) {
  const { items, alerts, schedule, loadError, refresh, reloadAlerts, putItem, dropItem } = useDashboardData();
  const { progress, checkAll, stop } = useCheckAll((result) => putItem(result.item));
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const closeNotice = useCallback(() => setNotice(null), []);

  const entries = useMemo(() => (items ?? []).map((item) => ({ item, summary: summarize(item) })), [items]);
  const sums = useMemo(() => totals(entries), [entries]);
  const counts = useMemo(
    () =>
      Object.fromEntries(
        FILTERS.map((one) => [one.value, entries.filter(({ summary }) => matches(summary, one.value)).length]),
      ) as Record<Filter, number>,
    [entries],
  );
  const deals = useMemo(() => sortItems(entries.filter(({ summary }) => isDeal(summary)), "deals").slice(0, 6), [entries]);
  const opened = entries.find(({ item }) => item.id === openId) ?? null;

  /** Celebrate new alerts, or say what adding or checking found. */
  function showResult(result: CheckResult, done: string, action?: Notice["action"]) {
    putItem(result.item);
    if (result.alerts.length) {
      setNotice({ kind: "alert", text: result.alerts.join(" · ") });
      reloadAlerts();
      confetti();
    } else if (result.errors.length) {
      const failed = result.errors.map((problem) => `${storeName(problem.site)}: ${problem.error}`).join(" ");
      setNotice({ kind: "error", text: `${done} Some stores couldn't be checked. ${failed}` });
    } else {
      const best = bestListing(result.item);
      const price = best ? ` ${formatRupees(best.last_price!)} on ${storeName(best.site)}.` : " It's out of stock right now.";
      setNotice({ kind: "success", text: `${done}${price}`, action });
    }
  }

  function onAdded(result: CheckResult) {
    const id = result.item.id;
    const setTarget = result.item.target_price === null ? { label: "Set a target", run: () => setOpenId(id) } : undefined;
    showResult(result, `Now tracking ${result.item.name}.`, setTarget);
  }

  function chooseFilter(next: Filter) {
    setFilter(next);
    document.getElementById("items")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  async function onCheckAll() {
    const summary = await checkAll(entries.map(({ item }) => item));
    if (!summary) return;     // the login was lost: the login page takes over
    if (summary.alerts.length) {
      setNotice({ kind: "alert", text: [...summary.alerts, describeCheckAll(summary)].join(" · ") });
      reloadAlerts();
      confetti();
    } else {
      setNotice({ kind: summary.failed ? "error" : "success", text: describeCheckAll(summary) });
    }
  }

  async function logOut() {
    try {
      await api.logOut();
    } catch {
      // The server is down: the login page will say so when it's needed.
    }
    onLoggedOut();
  }

  return (
    <div className="app">
      <a className="skip-link" href="#items">
        Skip to your items
      </a>
      <Header username={username} onAdded={onAdded} onLogOut={() => void logOut()}>
        <FilterTabs filter={filter} counts={counts} onChange={chooseFilter} />
        <ScheduleStatus schedule={schedule} />
      </Header>

      <main className="dashboard">
        {loadError && (
          <div className="banner" role="alert">
            <WarningIcon />
            <span>{loadError}</span>
            <button type="button" className="btn" onClick={() => void refresh()}>
              Try again
            </button>
          </div>
        )}

        <Greeting username={username} totals={sums} />
        <StatTiles totals={sums} onFilter={chooseFilter} />
        <DealsStrip deals={deals} onOpen={setOpenId} />

        <div className="dash-columns">
          <ItemsSection
            entries={entries}
            filter={filter}
            status={items !== null ? "ready" : loadError ? "failed" : "loading"}
            checking={progress}
            onCheckAll={() => void onCheckAll()}
            onStopChecking={stop}
            onOpen={setOpenId}
          />
          <aside className="side-column" aria-label="Alerts and daily checks">
            <AlertsPanel alerts={alerts} />
            <SchedulePanel schedule={schedule} />
          </aside>
        </div>
      </main>

      <footer className="site-footer">
        <span>
          <strong>Price Tracker</strong> · prices from Amazon.in and Flipkart · made with ☕ and a little impatience
        </span>
        <span className="muted">Not affiliated with Amazon or Flipkart.</span>
      </footer>

      {opened && (
        <ItemDrawer
          key={opened.item.id}
          item={opened.item}
          summary={opened.summary}
          onClose={() => setOpenId(null)}
          onChange={putItem}
          onRemove={(id) => {
            setOpenId(null);
            dropItem(id);
          }}
          onChecked={showResult}
          notify={setNotice}
        />
      )}
      <Toast notice={notice} onClose={closeNotice} />
    </div>
  );
}
