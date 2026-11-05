// Light, dark, or whatever the system uses. The choice is kept in this
// browser, and set on <html data-theme> before the page draws, so it never flashes.

export type ThemeChoice = "system" | "light" | "dark";

const KEY = "price-tracker-theme";

export function savedTheme(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";      // storage can be off, e.g. in some private windows
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    // Not kept for next time, but it still applies now.
  }
}

/** Whether the page is dark now, by choice or by the system's setting. */
export function isDark(choice: ThemeChoice): boolean {
  if (choice !== "system") return choice === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}
