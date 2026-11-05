import { useMemo, useState } from "react";

import { FILTERS, matches, sortItems, SORTS, type Filter, type ItemEntry, type Sort } from "../../lib/insights";
import { RefreshIcon, SearchIcon, Spinner, StopIcon } from "../common/Icons";
import { ItemCard } from "../items/ItemCard";
import { EmptyState, SkeletonGrid } from "./EmptyStates";

interface Props {
  /** Every tracked item, with its summary. */
  entries: ItemEntry[];
  /** Which items to show: the tab picked in the blue strip, or a tile. */
  filter: Filter;
  /** "loading" before the first answer; "failed" when it never came (a banner says why). */
  status: "loading" | "failed" | "ready";
  checking: { done: number; total: number } | null;
  onCheckAll: () => void;
  onStopChecking: () => void;
  onOpen: (itemId: number) => void;
}

/** The grid of item cards, with search, sorting and "Check all". */
export function ItemsSection({ entries, filter, status, checking, onCheckAll, onStopChecking, onOpen }: Props) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("deals");
  const info = FILTERS.find((one) => one.value === filter)!;
  const words = search.trim().toLowerCase();

  const visible = useMemo(() => {
    const shown = entries.filter(
      ({ item, summary }) => matches(summary, filter) && (!words || item.name.toLowerCase().includes(words)),
    );
    return sortItems(shown, sort);
  }, [entries, filter, words, sort]);

  return (
    <section id="items" className="items-section" aria-labelledby="items-heading">
      <div className="items-head">
        <h2 id="items-heading">
          {info.label} <span className="muted">({visible.length})</span>
        </h2>
        <div className="items-tools">
          <div className="search-box">
            <SearchIcon size={16} />
            <label htmlFor="item-search" className="sr-only">
              Search your items
            </label>
            <input
              id="item-search"
              type="search"
              placeholder="Search your items"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <label className="sort-select">
            <span className="sr-only">Sort by</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as Sort)}>
              {SORTS.map((one) => (
                <option key={one.value} value={one.value}>
                  {one.label}
                </option>
              ))}
            </select>
          </label>
          {checking ? (
            <button type="button" className="btn" onClick={onStopChecking}>
              <StopIcon /> Stop
            </button>
          ) : (
            <button type="button" className="btn btn-yellow" onClick={onCheckAll} disabled={!entries.length}>
              <RefreshIcon /> Check all
            </button>
          )}
        </div>
      </div>

      {checking && (
        <div className="check-progress" aria-live="polite">
          <span>
            <Spinner size={14} /> Checking {Math.min(checking.done + 1, checking.total)} of {checking.total}… going easy on
            the stores 🐢
          </span>
          <div className="progress-bar">
            <span style={{ width: `${(checking.done / checking.total) * 100}%` }} />
          </div>
        </div>
      )}

      {status === "loading" ? (
        <SkeletonGrid />
      ) : status === "failed" ? null : entries.length === 0 ? (
        <EmptyState />
      ) : visible.length === 0 ? (
        <p className="empty-filter">{words ? `Nothing called "${search.trim()}" here.` : info.empty}</p>
      ) : (
        <ul className="item-grid">
          {visible.map(({ item, summary }) => (
            <li key={item.id}>
              <ItemCard item={item} summary={summary} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
