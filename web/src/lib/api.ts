// Talks to the Python web API. Paths are relative, so the same code works
// behind the Vite dev server's proxy and when the API serves the built UI.
// The login is a cookie the browser keeps and sends by itself; it's HttpOnly,
// so no script on the page can read it.

export interface PricePoint {
  checked_at: string;
  price: number | null;
  in_stock: boolean;
}

/** What a store page's price history says. */
export interface ListingStats {
  lowest_price: number | null;
  highest_price: number | null;
  /** The middle price of the last 30 days of checks. */
  usual_price: number | null;
  /** The price at the check before the latest one. */
  previous_price: number | null;
  checks: number;
  /** The last 30 days, oldest first. */
  recent_prices: PricePoint[];
}

export interface Listing {
  id: number;
  site: string;
  product_id: string;
  url: string;
  title: string | null;
  image_url: string | null;
  last_price: number | null;
  last_in_stock: boolean | null;
  last_checked_at: string | null;
  last_error: string | null;
  stats: ListingStats | null;
}

export interface Item {
  id: number;
  name: string;
  target_price: number | null;
  active: boolean;
  created_at: string;
  listings: Listing[];
}

export interface CheckResult {
  item: Item;
  alerts: string[];
  errors: { listing_id: number; site: string; error: string }[];
}

export interface ListingHistory {
  listing_id: number;
  site: string;
  prices: PricePoint[];
}

export interface Alert {
  id: number;
  item_id: number;
  item_name: string;
  site: string;
  kind: "near_target" | "big_drop" | string;
  price: number;
  message: string;
  url: string;
  created_at: string;
  sent_at: string | null;
}

export interface LoginStatus {
  logged_in: boolean;
  username: string | null;
  /** false until an account is made with `python -m price_tracker user add NAME`. */
  has_accounts: boolean;
}

/** The daily checks Windows Task Scheduler runs. */
export interface Schedule {
  available: boolean;
  on: boolean;
  times: string[];
  next_check: string | null;
}

/** A request that failed. `message` is written for people. */
export class ApiError extends Error {
  readonly status: number;
  /** For 429: how many seconds to wait before trying again. */
  readonly retryAfter: number | null;

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

export const SERVER_DOWN =
  "Can't reach the Price Tracker server. Start it with: python -m price_tracker serve";

let loggedOutHandler: (() => void) | null = null;

/** Run `handler` when a request finds the login gone: it expired, or the password was changed. */
export function whenLoggedOut(handler: (() => void) | null): void {
  loggedOutHandler = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, SERVER_DOWN);
  }
  if (!response.ok) {
    const retryAfter = Number(response.headers.get("Retry-After")) || null;
    const error = new ApiError(response.status, await describeError(response), retryAfter);
    if (response.status === 401 && !path.startsWith("/auth/")) loggedOutHandler?.();
    throw error;
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

async function describeError(response: Response): Promise<string> {
  try {
    const { detail } = await response.json();
    if (typeof detail === "string") return detail;
    // FastAPI's validation errors are a list of {loc, msg}.
    if (Array.isArray(detail) && detail.length) {
      return detail.map((problem: { msg?: string }) => problem.msg).filter(Boolean).join(". ");
    }
  } catch {
    // Not JSON: the dev server couldn't reach the API, for example.
  }
  return response.status >= 500 && response.status !== 502
    ? SERVER_DOWN
    : `Something went wrong (HTTP ${response.status}).`;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const api = {
  loginStatus: () => request<LoginStatus>("/auth/status"),

  logIn: (username: string, password: string) =>
    request<LoginStatus>("/auth/login", { method: "POST", ...json({ username, password }) }),

  logOut: () => request<void>("/auth/logout", { method: "POST" }),

  listItems: () => request<Item[]>("/items"),

  addItem: (link: string, targetPrice: number | null) =>
    request<CheckResult>("/items", { method: "POST", ...json({ link, target_price: targetPrice }) }),

  addListing: (itemId: number, link: string) =>
    request<CheckResult>(`/items/${itemId}/listings`, { method: "POST", ...json({ link }) }),

  setTarget: (itemId: number, targetPrice: number | null) =>
    request<Item>(`/items/${itemId}`, { method: "PATCH", ...json({ target_price: targetPrice }) }),

  removeItem: (itemId: number) => request<void>(`/items/${itemId}`, { method: "DELETE" }),

  checkItem: (itemId: number) => request<CheckResult>(`/items/${itemId}/check`, { method: "POST" }),

  priceHistory: (itemId: number, days: number) =>
    request<ListingHistory[]>(`/items/${itemId}/history?days=${days}`),

  recentAlerts: (limit = 20) => request<Alert[]>(`/alerts?limit=${limit}`),

  schedule: () => request<Schedule>("/schedule"),
};

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
