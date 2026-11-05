import { useCallback, useEffect, useState } from "react";

import { LogoMark, Spinner, WarningIcon } from "./components/common/Icons";
import { api, errorMessage, whenLoggedOut } from "./lib/api";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";

type Auth =
  | { state: "loading" }
  | { state: "down"; message: string }
  | { state: "out"; hasAccounts: boolean; reason: string | null }
  | { state: "in"; username: string };

/** Asks the server who's logged in, then shows the login page or the dashboard. */
export default function App() {
  const [auth, setAuth] = useState<Auth>({ state: "loading" });

  const loadStatus = useCallback(async () => {
    try {
      const status = await api.loginStatus();
      setAuth(
        status.logged_in
          ? { state: "in", username: status.username ?? "there" }
          : { state: "out", hasAccounts: status.has_accounts, reason: null },
      );
    } catch (failure) {
      setAuth({ state: "down", message: errorMessage(failure) });
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  // A request found the login gone (it expired, or the password changed): back to the login page.
  useEffect(() => {
    whenLoggedOut(() =>
      setAuth({ state: "out", hasAccounts: true, reason: "Your login expired. Log in again to carry on." }),
    );
    return () => whenLoggedOut(null);
  }, []);

  switch (auth.state) {
    case "loading":
      return (
        <div className="splash">
          <LogoMark size={48} />
          <Spinner size={22} />
          <span className="sr-only">Loading</span>
        </div>
      );
    case "down":
      return (
        <div className="splash">
          <div className="banner" role="alert">
            <WarningIcon />
            <span>{auth.message}</span>
            <button type="button" className="btn" onClick={() => void loadStatus()}>
              Try again
            </button>
          </div>
        </div>
      );
    case "out":
      return (
        <LoginPage
          hasAccounts={auth.hasAccounts}
          reason={auth.reason}
          onLoggedIn={(status) => setAuth({ state: "in", username: status.username ?? "there" })}
        />
      );
    default:
      return (
        <DashboardPage
          username={auth.username}
          onLoggedOut={() => setAuth({ state: "out", hasAccounts: true, reason: null })}
        />
      );
  }
}
