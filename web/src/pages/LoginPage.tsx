import { useId, useState } from "react";

import { EyeIcon, EyeOffIcon, LogoMark, Spinner, WarningIcon } from "../components/common/Icons";
import { api, ApiError, errorMessage, type LoginStatus } from "../lib/api";

interface Props {
  hasAccounts: boolean;
  /** Why the login page is showing, like a login that expired. */
  reason?: string | null;
  onLoggedIn: (status: LoginStatus) => void;
}

const PERKS = [
  { emoji: "📉", title: "Every price, every day", text: "Amazon.in and Flipkart prices checked twice a day, with a chart of each." },
  { emoji: "🎯", title: "Your price, your rules", text: "Set a target and know the moment it's hit." },
  { emoji: "📲", title: "Pinged on Telegram", text: "Alerts land on your phone, so you never overpay again." },
];

export function LoginPage({ hasAccounts, reason, onLoggedIn }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const userId = useId();
  const passwordId = useId();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("Type your username and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onLoggedIn(await api.logIn(username.trim(), password));
    } catch (failure) {
      setError(errorMessage(failure));
      if (failure instanceof ApiError && failure.status === 401) setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero" aria-label="About Price Tracker">
        <div className="brand brand-large">
          <LogoMark size={44} />
          <span className="brand-name">
            Price<span>Tracker</span>
          </span>
        </div>
        <h1>
          Never overpay again <span aria-hidden="true">💸</span>
        </h1>
        <p className="login-lead">Your personal deal radar for Amazon.in and Flipkart.</p>
        <ul className="perks">
          {PERKS.map((perk) => (
            <li key={perk.title}>
              <span className="perk-emoji" aria-hidden="true">
                {perk.emoji}
              </span>
              <span>
                <strong>{perk.title}</strong>
                <span>{perk.text}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="login-card-wrap">
        <form className="login-card" onSubmit={submit} noValidate aria-labelledby="login-heading">
          <h2 id="login-heading">Welcome back 👋</h2>
          <p className="muted">Log in to see your deals.</p>

          {reason && <p className="notice-box">{reason}</p>}

          {!hasAccounts && (
            <div className="notice-box">
              <strong>No account yet.</strong> In the project folder, make one with:
              <code className="command">python -m price_tracker user add YOUR-NAME</code>
              Then log in here.
            </div>
          )}

          <label htmlFor={userId}>Username</label>
          <input
            id={userId}
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={busy}
            autoFocus
          />

          <label htmlFor={passwordId}>Password</label>
          <div className="password-input">
            <input
              id={passwordId}
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
              aria-invalid={error ? true : undefined}
            />
            <button
              type="button"
              className="icon-button"
              onClick={() => setShowPassword((shown) => !shown)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeOffIcon size={18} /> : <EyeIcon size={18} />}
            </button>
          </div>

          {error && (
            <p className="message error" role="alert">
              <WarningIcon /> {error}
            </p>
          )}

          <button type="submit" className="btn btn-yellow btn-block" disabled={busy}>
            {busy && <Spinner />} {busy ? "Logging in…" : "Log in"}
          </button>
          <p className="login-foot muted small">
            Forgot it? Set a new one with <code>python -m price_tracker user password NAME</code>
          </p>
        </form>
      </section>
    </div>
  );
}
