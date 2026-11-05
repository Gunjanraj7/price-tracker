import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError, errorMessage, type Alert, type Item, type Schedule } from "../lib/api";

/** Coming back to the tab reloads the data, but not more often than this. */
const RELOAD_GAP_MS = 30_000;

/**
 * Everything the dashboard shows: the items, the newest alerts and whether the
 * daily checks are on. Loaded now, and again when you come back to the tab,
 * since the daily checks may have run in the meantime.
 */
export function useDashboardData() {
  const [items, setItems] = useState<Item[] | null>(null);      // null until the first load
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const lastLoad = useRef(0);

  const refresh = useCallback(async () => {
    lastLoad.current = Date.now();
    try {
      const [freshItems, freshAlerts] = await Promise.all([api.listItems(), api.recentAlerts()]);
      setItems(freshItems);
      setAlerts(freshAlerts);
      setLoadError(null);
    } catch (failure) {
      // A lost login sends you to the login page by itself (see whenLoggedOut).
      if (!(failure instanceof ApiError && failure.status === 401)) setLoadError(errorMessage(failure));
      return;
    }
    api.schedule().then(setSchedule, () => {});
  }, []);

  useEffect(() => {
    void refresh();
    const onFocus = () => {
      if (Date.now() - lastLoad.current >= RELOAD_GAP_MS) void refresh();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  const reloadAlerts = useCallback(() => {
    api.recentAlerts().then(setAlerts, () => {});
  }, []);

  /** Put a new or changed item in the list. */
  const putItem = useCallback((item: Item) => {
    setItems((current) => {
      const list = current ?? [];
      return list.some((one) => one.id === item.id) ? list.map((one) => (one.id === item.id ? item : one)) : [...list, item];
    });
  }, []);

  const dropItem = useCallback((itemId: number) => {
    setItems((current) => current?.filter((one) => one.id !== itemId) ?? null);
  }, []);

  return { items, alerts, schedule, loadError, refresh, reloadAlerts, putItem, dropItem };
}
