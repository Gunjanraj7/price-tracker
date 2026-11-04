import { useId, useState } from "react";

import { api, errorMessage, type CheckResult } from "../api";
import { parsePrice } from "../format";
import { PlusIcon, Spinner, WarningIcon } from "./Icons";

interface Props {
  onAdded: (result: CheckResult) => void;
}

/** Paste a link, optionally set a target, and start tracking. */
export function AddItemForm({ onAdded }: Props) {
  const [link, setLink] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const linkId = useId();
  const targetId = useId();
  const helpId = useId();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const targetPrice = parsePrice(target);
    if (!link.trim()) {
      setError("Paste a product link from Amazon.in or Flipkart first.");
      return;
    }
    if (Number.isNaN(targetPrice)) {
      setError("Write the target price as a number, like 1500 or 1,499.50.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onAdded(await api.addItem(link.trim(), targetPrice));
      setLink("");
      setTarget("");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card add-form" onSubmit={submit} noValidate>
      <h2 className="card-title">Track a product</h2>
      <div className="add-fields">
        <div className="field field-link">
          <label htmlFor={linkId}>Product link</label>
          <input
            id={linkId}
            type="text"
            inputMode="url"
            autoComplete="off"
            placeholder="Paste an Amazon.in or Flipkart link"
            value={link}
            onChange={(event) => setLink(event.target.value)}
            disabled={busy}
            aria-describedby={helpId}
            aria-invalid={error ? true : undefined}
          />
        </div>
        <div className="field field-target">
          <label htmlFor={targetId}>
            Alert me at <span className="optional">(optional)</span>
          </label>
          <div className="rupee-input">
            <span aria-hidden="true">₹</span>
            <input
              id={targetId}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              placeholder="1,500"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              disabled={busy}
            />
          </div>
        </div>
        <button className="button primary add-button" type="submit" disabled={busy}>
          {busy ? <Spinner /> : <PlusIcon />}
          {busy ? "Getting the price…" : "Start tracking"}
        </button>
      </div>
      <p id={helpId} className="hint" aria-live="polite">
        {busy
          ? "Reading the store page. This takes a few seconds."
          : "The whole message the store app shares works too. You'll get an alert when the price gets close to your target, or drops 30% below its usual price."}
      </p>
      {error && (
        <p className="message error" role="alert">
          <WarningIcon /> {error}
        </p>
      )}
    </form>
  );
}
