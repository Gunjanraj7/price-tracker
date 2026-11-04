// Talks to the Python web API. Paths are relative, so the same code works
// behind the Vite dev server's proxy and when the API serves the built UI.

export interface Listing {
  id: number;
  site: string;
  product_id: string;
  url: string;
  title: string | null;
  last_price: number | null;
  last_in_stock: boolean | null;
  last_checked_at: string | null;
  last_error: string | null;
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

export interface PricePoint {
  checked_at: string;
  price: number | null;
  in_stock: boolean;
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

/** A request that failed. `message` is written for people. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const SERVER_DOWN =
  "Can't reach the Price Tracker server. Start it with: python -m price_tracker serve";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, SERVER_DOWN);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await describeError(response));
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
};

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
