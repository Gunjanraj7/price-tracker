import type { Alert } from "../api";
import { timeAgo } from "../format";
import { BellIcon, CheckIcon } from "./Icons";

const KINDS: Record<string, string> = { near_target: "Near your target", big_drop: "Big drop" };

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="card alerts" aria-labelledby="alerts-heading">
      <h2 id="alerts-heading" className="card-title">
        <BellIcon /> Recent alerts
      </h2>
      {alerts.length === 0 ? (
        <p className="muted">
          No alerts yet. When a price gets close to your target, or drops 30% below its usual price, it shows up
          here and on Telegram.
        </p>
      ) : (
        <ul className="alert-list">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <span className="badge">{KINDS[alert.kind] ?? alert.kind}</span>
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
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
