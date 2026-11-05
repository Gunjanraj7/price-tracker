import { useEffect } from "react";

import { BellIcon, CheckIcon, WarningIcon } from "../common/Icons";

/** A short message for the toast, with an optional button, like "Set a target". */
export type Notice = {
  kind: "success" | "error" | "alert";
  text: string;
  action?: { label: string; run: () => void };
};

const ICONS = { success: CheckIcon, error: WarningIcon, alert: BellIcon };

/** A short message at the bottom of the screen that goes away by itself. */
export function Toast({ notice, onClose }: { notice: Notice | null; onClose: () => void }) {
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(onClose, notice.kind === "success" && !notice.action ? 6000 : 10000);
    return () => clearTimeout(timer);
  }, [notice, onClose]);

  const Icon = notice ? ICONS[notice.kind] : null;
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {notice && Icon && (
        <div className={`toast ${notice.kind}`}>
          <Icon />
          <span>{notice.text}</span>
          {notice.action && (
            <button
              type="button"
              className="toast-action"
              onClick={() => {
                notice.action!.run();
                onClose();
              }}
            >
              {notice.action.label}
            </button>
          )}
          <button type="button" className="toast-close" onClick={onClose} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
    </div>
  );
}
