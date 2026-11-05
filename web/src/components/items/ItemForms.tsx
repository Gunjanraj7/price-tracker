import { useId, useState } from "react";

import { formatRupees, parsePrice, storeName } from "../../lib/format";
import { PlusIcon, Spinner, TargetIcon } from "../common/Icons";

interface TargetFormProps {
  target: number | null;
  /** Prices worth suggesting as a target, like the lowest seen so far. */
  suggestions: { label: string; price: number }[];
  busy: boolean;
  onSave: (price: number | null) => void;
}

/** Set, change or remove an item's target price. */
export function TargetForm({ target, suggestions, busy, onSave }: TargetFormProps) {
  const [text, setText] = useState(target === null ? "" : String(target));
  const [problem, setProblem] = useState<string | null>(null);
  const inputId = useId();
  const problemId = useId();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const price = parsePrice(text);
    if (price === null || Number.isNaN(price)) {
      setProblem("Write the price you'd like to pay, like 1500 or 1,499.50.");
      return;
    }
    setProblem(null);
    onSave(price);
  }

  return (
    <form className="target-form" onSubmit={submit} noValidate>
      <label htmlFor={inputId}>Alert me when the price gets close to</label>
      <div className="inline-row">
        <div className="rupee-input">
          <span aria-hidden="true">₹</span>
          <input
            id={inputId}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            placeholder="1,500"
            value={text}
            onChange={(event) => setText(event.target.value)}
            disabled={busy}
            aria-invalid={problem ? true : undefined}
            aria-describedby={problem ? problemId : undefined}
          />
        </div>
        <button type="submit" className="btn btn-yellow" disabled={busy}>
          {busy ? <Spinner /> : <TargetIcon />} Save target
        </button>
        {target !== null && (
          <button type="button" className="btn" onClick={() => onSave(null)} disabled={busy}>
            Remove target
          </button>
        )}
      </div>
      {suggestions.length > 0 && (
        <div className="suggestions" aria-label="Suggested targets">
          <span className="muted">Try:</span>
          {suggestions.map((suggestion) => (
            <button
              key={suggestion.label}
              type="button"
              className="chip"
              disabled={busy}
              onClick={() => setText(String(suggestion.price))}
            >
              {suggestion.label} {formatRupees(suggestion.price)}
            </button>
          ))}
        </div>
      )}
      {problem && (
        <p id={problemId} className="message error">
          {problem}
        </p>
      )}
    </form>
  );
}

/** Add the same product's page on the other store. */
export function LinkForm({ stores, busy, onAdd }: { stores: string[]; busy: boolean; onAdd: (link: string) => void }) {
  const [link, setLink] = useState("");
  const inputId = useId();
  const names = stores.map(storeName).join(" or ");

  return (
    <form
      className="link-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (link.trim()) onAdd(link.trim());
      }}
    >
      <label htmlFor={inputId}>The same product on {names}</label>
      <div className="inline-row">
        <input
          id={inputId}
          type="text"
          inputMode="url"
          autoComplete="off"
          placeholder={`Paste the ${names} link`}
          value={link}
          onChange={(event) => setLink(event.target.value)}
          disabled={busy}
          className="grow"
        />
        <button type="submit" className="btn" disabled={busy || !link.trim()}>
          {busy ? <Spinner /> : <PlusIcon />} {busy ? "Getting the price…" : `Add ${names}`}
        </button>
      </div>
      <p className="hint">Then you'll see both stores' prices side by side, and the cheaper one wins 🏁</p>
    </form>
  );
}
