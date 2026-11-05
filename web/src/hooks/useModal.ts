import { useEffect, useRef } from "react";

/**
 * Make `panel` behave as a modal dialog: focus starts on `first`, Tab stays
 * inside, Escape calls `onClose`, and the page behind doesn't scroll. Focus goes
 * back where it was when the panel closes.
 */
export function useModal(
  panel: React.RefObject<HTMLElement | null>,
  first: React.RefObject<HTMLElement | null>,
  onClose: () => void,
): void {
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    first.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = [
        ...panel.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input:not([disabled]), select, [tabindex='0']"),
      ];
      if (!focusable.length) return;
      const [start, end] = [focusable[0], focusable[focusable.length - 1]];
      if (event.shiftKey && document.activeElement === start) {
        event.preventDefault();
        end.focus();
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault();
        start.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, [panel, first]);
}
