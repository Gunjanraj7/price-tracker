import { FILTERS, type Filter } from "../../lib/insights";

interface Props {
  filter: Filter;
  counts: Record<Filter, number>;
  onChange: (filter: Filter) => void;
}

/** The tabs in the blue strip under the header: which items to show, and how many there are. */
export function FilterTabs({ filter, counts, onChange }: Props) {
  return (
    <div className="filter-tabs" role="group" aria-label="Show">
      {FILTERS.map((one) => (
        <button key={one.value} type="button" aria-pressed={filter === one.value} onClick={() => onChange(one.value)}>
          <span aria-hidden="true">{one.emoji}</span> {one.label}
          <span className="count">{counts[one.value]}</span>
        </button>
      ))}
    </div>
  );
}
