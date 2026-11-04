import { useEffect } from "react";

import { BellIcon, CheckIcon, WarningIcon } from "./Icons";
import type { Notice } from "./ItemCard";

const ICONS = { success: CheckIcon, error: WarningIcon, alert: BellIcon };

/** A short message at the bottom of the screen that goes away by itself. */
export function Toast({ notice, onClose }: { notice: Notice | null; onClose: () => void }) {
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(onClose, notice.kind === "error" ? 9000 : 6000);
    return () => clearTimeout(timer);
  }, [notice, onClose]);

  const Icon = notice ? ICONS[notice.kind] : null;
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {notice && Icon && (
        <div className={`toast ${notice.kind}`}>
          <Icon />
          <span>{notice.text}</span>
          <button type="button" className="toast-close" onClick={onClose} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
    </div>
  );
}
