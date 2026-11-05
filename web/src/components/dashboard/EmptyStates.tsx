/** What shows before anything is tracked: three steps to start. */
export function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-emoji" aria-hidden="true">
        🛒
      </div>
      <h3>Nothing tracked yet</h3>
      <p className="muted">Three steps and you're hunting deals:</p>
      <ol>
        <li>
          <strong>Copy</strong> a product link: in the Amazon or Flipkart app, tap <em>Share</em>, then <em>Copy</em>.
        </li>
        <li>
          <strong>Paste</strong> it in the bar at the top and press <em>Track</em>. Add a target price if you have one in
          mind.
        </li>
        <li>
          <strong>Relax.</strong> Prices are checked twice a day, and you get a Telegram ping when it's time to buy 📲
        </li>
      </ol>
    </div>
  );
}

/** Grey cards that shimmer while the items load. */
export function SkeletonGrid() {
  return (
    <ul className="item-grid" aria-label="Loading your items">
      {[0, 1, 2].map((key) => (
        <li key={key}>
          <div className="item-card skeleton" aria-hidden="true">
            <div className="skeleton-media" />
            <div className="item-card-body">
              <div className="skeleton-line wide" />
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
