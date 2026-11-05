import { useRef, useState } from "react";

import { api, ApiError, type CheckResult, type Item } from "../lib/api";
import { plural } from "../lib/format";

export interface CheckAllSummary {
  /** Items checked, whether or not every store answered. */
  checked: number;
  /** Items skipped because they were checked a moment ago. */
  skipped: number;
  /** Items with a store that couldn't be checked. */
  failed: number;
  alerts: string[];
}

/**
 * "Check all": check every item, one after another, with progress and a way to
 * stop. The server spaces out the store visits, and skips pages checked in the
 * last few minutes. `onChecked` gets each item's fresh result as it comes in.
 */
export function useCheckAll(onChecked: (result: CheckResult) => void) {
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const stopped = useRef(false);

  /** Check `items`. Returns what happened, or null when the login was lost on the way. */
  async function checkAll(items: Item[]): Promise<CheckAllSummary | null> {
    stopped.current = false;
    const summary: CheckAllSummary = { checked: 0, skipped: 0, failed: 0, alerts: [] };
    setProgress({ done: 0, total: items.length });
    try {
      for (const [index, item] of items.entries()) {
        if (stopped.current) break;
        try {
          const result = await api.checkItem(item.id);
          onChecked(result);
          summary.alerts.push(...result.alerts);
          if (result.errors.length) summary.failed++;
          summary.checked++;
        } catch (failure) {
          if (failure instanceof ApiError && failure.status === 401) return null;
          if (failure instanceof ApiError && failure.status === 429) {
            summary.skipped++;
          } else {
            summary.failed++;
            summary.checked++;
          }
        }
        setProgress({ done: index + 1, total: items.length });
      }
    } finally {
      setProgress(null);
    }
    return summary;
  }

  return { progress, checkAll, stop: () => (stopped.current = true) };
}

/** What a "Check all" found, in a sentence or three. */
export function describeCheckAll({ checked, skipped, failed }: CheckAllSummary): string {
  const parts = [`Checked ${plural(checked, "item")}.`];
  if (skipped) parts.push(`${plural(skipped, "item")} had just been checked, so we skipped ${skipped === 1 ? "it" : "them"}.`);
  if (failed) parts.push(`${failed} couldn't be checked: see Needs attention.`);
  return parts.join(" ");
}
