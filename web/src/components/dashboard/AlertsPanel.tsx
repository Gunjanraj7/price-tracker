import type { Alert } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { BellIcon, CheckIcon } from "../common/Icons";

const KINDS: Record<string, { emoji: string; label: string }> = {
  near_target: { emoji: "🎯", label: "Near your target" },
  big_drop: { emoji: "📉", label: "Big drop" },
};

const WEEK_MS = 7 * 24 * 3600_000;

/** The newest alerts, the same ones that went to Telegram. */
export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  const thisWeek = alerts.filter((alert) => Date.now() - Date.parse(alert.created_at) < WEEK_MS).length;
  return (
    <section className="panel alerts" aria-labelledby="alerts-heading">
      <h2 id="alerts-heading" className="panel-title">
        <BellIcon /> Alerts
        {thisWeek > 0 && <span className="badge">{thisWeek} this week</span>}
      </h2>
      {alerts.length === 0 ? (
        <p className="muted small">
          No alerts yet. When a price gets close to your target, or drops 30% below its usual price, it pops up here and on
          Telegram 📲
        </p>
      ) : (
        <ul className="alert-list">
          {alerts.map((alert) => {
            const kind = KINDS[alert.kind] ?? { emoji: "🔔", label: alert.kind };
            return (
              <li key={alert.id}>
                <span className="alert-emoji" aria-hidden="true">
                  {kind.emoji}
                </span>
                <div>
                  <span className="alert-kind">{kind.label}</span>
                  <a className="alert-message" href={alert.url} target="_blank" rel="noopener noreferrer">
                    {alert.message}
                  </a>
                  <span className="alert-meta">
                    {timeAgo(alert.created_at)}
                    {alert.sent_at && (
                      <>
                        {" · "}
                        <CheckIcon size={12} /> sent to Telegram
                      </>
                    )}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
