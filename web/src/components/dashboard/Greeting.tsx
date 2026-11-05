import { plural } from "../../lib/format";
import type { Totals } from "../../lib/insights";

/** "Hey gunjan 👋", and the one thing worth knowing right now. */
export function Greeting({ username, totals }: { username: string; totals: Totals }) {
  let line: string;
  if (!totals.items) line = "Paste a product link above to start the hunt 🕵️";
  else if (totals.targetHit) line = `🎯 ${plural(totals.targetHit, "item")} hit your target. Treat yourself?`;
  else if (totals.deals) line = `🔥 ${plural(totals.deals, "deal")} worth a look today.`;
  else if (totals.dropped) line = `📉 ${plural(totals.dropped, "price")} dropped since the last check.`;
  else line = "No big drops yet. We're watching the prices for you 👀";
  return (
    <div className="greeting">
      <h1>
        Hey {username} <span aria-hidden="true">👋</span>
      </h1>
      <p>{line}</p>
    </div>
  );
}
