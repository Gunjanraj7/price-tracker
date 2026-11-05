import { useId, useState } from "react";

import { api, errorMessage, type CheckResult } from "../../lib/api";
import { parsePrice } from "../../lib/format";
import { applyTheme, isDark, savedTheme, type ThemeChoice } from "../../lib/theme";
import { LinkIcon, LogoMark, LogoutIcon, MoonIcon, SearchIcon, Spinner, SunIcon, WarningIcon } from "../common/Icons";

interface Props {
  username: string;
  onAdded: (result: CheckResult) => void;
  onLogOut: () => void;
  /** The blue strip under the bar: filters and the daily-check status. */
  children?: React.ReactNode;
}

/** The dark bar on top, like Amazon's: the brand, a big "paste a link" box, and your account. */
export function Header({ username, onAdded, onLogOut, children }: Props) {
  return (
    <header className="site-header">
      <div className="header-main">
        <a className="brand" href="/" aria-label="Price Tracker home">
          <LogoMark />
          <span className="brand-name">
            Price<span>Tracker</span>
          </span>
        </a>
        <AddBar onAdded={onAdded} />
        <div className="header-actions">
          <ThemeToggle />
          <div className="account">
            <span className="account-hello">Hello, {username}</span>
            <button type="button" className="account-logout" onClick={onLogOut}>
              <LogoutIcon size={14} /> Log out
            </button>
          </div>
        </div>
      </div>
      {children && <div className="subnav">{children}</div>}
    </header>
  );
}

/** Paste a link, optionally a target, and start tracking: the header's search box. */
export function AddBar({ onAdded }: { onAdded: (result: CheckResult) => void }) {
  const [link, setLink] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const linkId = useId();
  const targetId = useId();

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
    <div className="add-bar-wrap">
      <form className={`add-bar ${error ? "has-error" : ""}`} onSubmit={submit} noValidate aria-label="Track a product">
        <span className="add-bar-icon" aria-hidden="true">
          <LinkIcon size={18} />
        </span>
        <label htmlFor={linkId} className="sr-only">
          Product link
        </label>
        <input
          id={linkId}
          className="add-bar-link"
          type="text"
          inputMode="url"
          autoComplete="off"
          placeholder="Paste an Amazon.in or Flipkart link…"
          value={link}
          onChange={(event) => setLink(event.target.value)}
          disabled={busy}
          aria-invalid={error ? true : undefined}
        />
        <label htmlFor={targetId} className="sr-only">
          Target price (optional)
        </label>
        <div className="add-bar-target">
          <span aria-hidden="true">₹</span>
          <input
            id={targetId}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            placeholder="Target"
            title="Optional: get an alert when the price gets close to this"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            disabled={busy}
          />
        </div>
        <button className="add-bar-button" type="submit" disabled={busy}>
          {busy ? <Spinner size={18} /> : <SearchIcon size={18} />}
          <span>{busy ? "Fetching…" : "Track"}</span>
        </button>
      </form>
      {busy && (
        <p className="add-bar-note" aria-live="polite">
          Reading the store page… a few seconds ⏳
        </p>
      )}
      {error && (
        <p className="add-bar-note error" role="alert">
          <WarningIcon size={14} /> {error}
        </p>
      )}
    </div>
  );
}

const NEXT: Record<ThemeChoice, ThemeChoice> = { system: "dark", dark: "light", light: "system" };
const NAMES: Record<ThemeChoice, string> = { system: "the system's theme", dark: "dark mode", light: "light mode" };

/** Cycles through system → dark → light. */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(savedTheme);
  const dark = isDark(choice);
  const next = NEXT[choice];
  return (
    <button
      type="button"
      className="icon-button theme-toggle"
      onClick={() => {
        applyTheme(next);
        setChoice(next);
      }}
      aria-label={`Using ${NAMES[choice]}. Switch to ${NAMES[next]}`}
      title={`Using ${NAMES[choice]}`}
    >
      {dark ? <MoonIcon size={18} /> : <SunIcon size={18} />}
      {choice === "system" && <span className="auto-dot" aria-hidden="true" />}
    </button>
  );
}
