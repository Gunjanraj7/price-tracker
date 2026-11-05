import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { Item, Listing, ListingStats } from "./lib/api";

const AMAZON = "https://www.amazon.in/dp/B0D3DK779N";
const FLIPKART = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT";
const now = new Date().toISOString();
const hoursFromNow = (hours: number) => new Date(Date.now() + hours * 3600_000).toISOString();

function makeStats(changes: Partial<ListingStats> = {}): ListingStats {
  return {
    lowest_price: 1199,
    highest_price: 1499,
    usual_price: 1399,
    previous_price: 1399,
    checks: 6,
    recent_prices: [
      { checked_at: "2026-11-03T03:30:00Z", price: 1499, in_stock: true },
      { checked_at: "2026-11-04T03:30:00Z", price: 1399, in_stock: true },
      { checked_at: "2026-11-05T03:30:00Z", price: 1299, in_stock: true },
    ],
    ...changes,
  };
}

function makeListing(changes: Partial<Listing> = {}): Listing {
  return {
    id: 1,
    site: "amazon",
    product_id: "B0D3DK779N",
    url: AMAZON,
    title: "boAt Airdopes 131",
    image_url: "https://m.media-amazon.com/images/I/31wu8gbDFYL._SY300_.jpg",
    last_price: 1299,
    last_in_stock: true,
    last_checked_at: now,
    last_error: null,
    stats: makeStats(),
    ...changes,
  };
}

/** boAt Airdopes at ₹1,299 on Amazon: 7% below its usual ₹1,399, ₹299 above its ₹1,000 target. */
function makeItem(changes: Partial<Item> = {}): Item {
  return {
    id: 1,
    name: "boAt Airdopes 131",
    target_price: 1000,
    active: true,
    created_at: now,
    listings: [makeListing()],
    ...changes,
  };
}

const flipkartListing = (changes: Partial<Listing> = {}) =>
  makeListing({ id: 2, site: "flipkart", product_id: "ACCHDYCG92CUSJFT", url: FLIPKART, last_price: 1249, ...changes });

type Route = (body: unknown) => unknown;

const LOGGED_IN: Record<string, Route> = {
  "GET /api/auth/status": () => ({ logged_in: true, username: "gunjan", has_accounts: true }),
  "GET /api/items": () => [],
  "GET /api/alerts?limit=20": () => [],
  "GET /api/schedule": () => ({ available: true, on: true, times: ["09:00", "21:00"], next_check: hoursFromNow(3) }),
  "GET /api/items/1/history?days=30": () => [],
};

/** Answer fetch() from `routes` (on top of a logged-in server), keyed "METHOD /api/path". Returns the requests made. */
function fakeServer(routes: Record<string, Route> = {}) {
  const all = { ...LOGGED_IN, ...routes };
  const requests: { key: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url}`;
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ key, body });
      const answer = all[key] ? all[key](body) : new Response(null, { status: 404 });
      if (answer instanceof Response) return answer;
      return new Response(answer === undefined ? null : JSON.stringify(answer), { status: answer === undefined ? 204 : 200 });
    }),
  );
  return requests;
}

const failWith =
  (status: number, detail: string, headers: Record<string, string> = {}) =>
  () =>
    new Response(JSON.stringify({ detail }), { status, headers });

const card = (name = "boAt Airdopes 131") => screen.getByRole("article", { name });
const tile = (label: string) => within(screen.getByRole("region", { name: "Summary" })).getByRole("button", { name: new RegExp(label) });

async function openDetails(name = "boAt Airdopes 131") {
  fireEvent.click(within(await screen.findByRole("article", { name })).getByRole("button", { name: "Details" }));
  return screen.getByRole("dialog", { name });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("logging in", () => {
  it("asks to log in, then shows the dashboard", async () => {
    const requests = fakeServer({
      "GET /api/auth/status": () => ({ logged_in: false, username: null, has_accounts: true }),
      "POST /api/auth/login": () => ({ logged_in: true, username: "gunjan", has_accounts: true }),
    });
    render(<App />);

    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: " gunjan " } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a long password" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("heading", { name: /Hey gunjan/ })).toBeTruthy();
    expect(requests.find((request) => request.key === "POST /api/auth/login")?.body).toEqual({
      username: "gunjan",
      password: "a long password",
    });
  });

  it("explains how to make the first account", async () => {
    fakeServer({ "GET /api/auth/status": () => ({ logged_in: false, username: null, has_accounts: false }) });
    render(<App />);
    expect(await screen.findByText("No account yet.")).toBeTruthy();
    expect(screen.getByText("python -m price_tracker user add YOUR-NAME")).toBeTruthy();
  });

  it("says why a login failed and clears the password", async () => {
    fakeServer({
      "GET /api/auth/status": () => ({ logged_in: false, username: null, has_accounts: true }),
      "POST /api/auth/login": failWith(401, "Wrong username or password."),
    });
    render(<App />);

    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "gunjan" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not it" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Wrong username or password.");
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
  });

  it("shows and hides the password", async () => {
    fakeServer({ "GET /api/auth/status": () => ({ logged_in: false, username: null, has_accounts: true }) });
    render(<App />);
    const password = (await screen.findByLabelText("Password")) as HTMLInputElement;
    expect(password.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password.type).toBe("text");
  });

  it("goes back to the login page when the login expires", async () => {
    fakeServer({ "GET /api/items": failWith(401, "Please log in.") });
    render(<App />);
    expect(await screen.findByText(/Your login expired/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Log in" })).toBeTruthy();
  });

  it("logs out", async () => {
    const requests = fakeServer({ "POST /api/auth/logout": () => undefined });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("button", { name: "Log in" })).toBeTruthy();
    expect(requests.some((request) => request.key === "POST /api/auth/logout")).toBe(true);
  });

  it("says when the server isn't running", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain("python -m price_tracker serve");
  });
});

describe("the dashboard", () => {
  it("shows each item's price, its verdict and how far it is from the target", async () => {
    fakeServer({ "GET /api/items": () => [makeItem()] });
    render(<App />);

    const item = await screen.findByRole("article", { name: "boAt Airdopes 131" });
    expect(within(item).getByText("₹1,299")).toBeTruthy();
    expect(within(item).getByText("Good price")).toBeTruthy();
    expect(within(item).getByText(/7% below usual/)).toBeTruthy();
    expect(within(item).getByText(/▼ ₹100 since last check/)).toBeTruthy();
    expect(within(item).getByText(/₹299 to go/)).toBeTruthy();
    expect(within(item).getByRole("link", { name: /Buy boAt Airdopes 131 on Amazon/ }).getAttribute("href")).toBe(AMAZON);
    expect(item.querySelector("img")?.getAttribute("src")).toContain("m.media-amazon.com");

    expect(tile("Tracking").textContent).toContain("1");
    expect(tile("Price drops").textContent).toContain("1");
    expect(tile("Could save").textContent).toContain("₹100");
    expect(screen.getByText(/Auto-check on · next in 3 hours/)).toBeTruthy();
    expect(screen.getByText(/No alerts yet/)).toBeTruthy();
  });

  it("puts the best deals up top and celebrates a hit target", async () => {
    const hit = makeItem({ listings: [makeListing({ last_price: 999, stats: makeStats({ previous_price: 1299 }) })] });
    fakeServer({ "GET /api/items": () => [hit] });
    render(<App />);

    await screen.findByRole("article", { name: "boAt Airdopes 131" });
    expect(within(card()).getByText("Target hit")).toBeTruthy();
    expect(within(card()).getByText(/Target hit! ₹1,000 or less/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Hot right now/ })).toBeTruthy();
    expect(screen.getByText(/1 item hit your target/)).toBeTruthy();
    expect(tile("Target hit").textContent).toContain("1");
  });

  it("explains how to start when nothing is tracked", async () => {
    fakeServer();
    render(<App />);
    expect(await screen.findByText("Nothing tracked yet")).toBeTruthy();
    expect(screen.getByText(/start the hunt/)).toBeTruthy();
  });

  it("starts tracking a pasted link", async () => {
    const requests = fakeServer({ "POST /api/items": () => ({ item: makeItem(), alerts: [], errors: [] }) });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: `Check this out ${AMAZON}` } });
    fireEvent.change(screen.getByLabelText("Target price (optional)"), { target: { value: "1,000" } });
    fireEvent.click(screen.getByRole("button", { name: "Track" }));

    expect(await screen.findByRole("article", { name: "boAt Airdopes 131" })).toBeTruthy();
    expect(requests.find((request) => request.key === "POST /api/items")?.body).toEqual({
      link: `Check this out ${AMAZON}`,
      target_price: 1000,
    });
    expect(screen.getByRole("status").textContent).toContain("Now tracking boAt Airdopes 131. ₹1,299 on Amazon.");
  });

  it("offers to set a target after adding without one", async () => {
    fakeServer({ "POST /api/items": () => ({ item: makeItem({ target_price: null }), alerts: [], errors: [] }) });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: AMAZON } });
    fireEvent.click(screen.getByRole("button", { name: "Track" }));
    fireEvent.click(await screen.findByRole("button", { name: "Set a target" }));
    const details = screen.getByRole("dialog", { name: "boAt Airdopes 131" });
    expect(within(details).getByLabelText("Alert me when the price gets close to")).toBeTruthy();
  });

  it("shows why a link couldn't be added", async () => {
    fakeServer({ "POST /api/items": failWith(422, "Only links from amazon.in, flipkart.com are supported, got: example.com") });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: "https://example.com/x" } });
    fireEvent.click(screen.getByRole("button", { name: "Track" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Only links from amazon.in");
  });

  it("refuses a target that isn't a price before asking the server", async () => {
    const requests = fakeServer();
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: AMAZON } });
    fireEvent.change(screen.getByLabelText("Target price (optional)"), { target: { value: "cheap" } });
    fireEvent.click(screen.getByRole("button", { name: "Track" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Write the target price as a number");
    expect(requests.some((request) => request.key === "POST /api/items")).toBe(false);
  });

  it("filters by the tabs and by searching", async () => {
    const hit = makeItem({ listings: [makeListing({ last_price: 999 })] });
    const pricey = makeItem({
      id: 2,
      name: "Sony WH-1000XM5",
      target_price: null,
      listings: [makeListing({ id: 3, product_id: "B0B1", last_price: 29990, stats: makeStats({ usual_price: 26990, previous_price: 29990 }) })],
    });
    fakeServer({ "GET /api/items": () => [hit, pricey] });
    render(<App />);
    await screen.findByRole("article", { name: "Sony WH-1000XM5" });
    expect(within(card("Sony WH-1000XM5")).getByText("Pricey rn")).toBeTruthy();

    fireEvent.click(within(screen.getByRole("group", { name: "Show" })).getByRole("button", { name: /Target hit/ }));
    expect(screen.queryByRole("article", { name: "Sony WH-1000XM5" })).toBeNull();
    expect(card()).toBeTruthy();

    fireEvent.click(within(screen.getByRole("group", { name: "Show" })).getByRole("button", { name: /All items/ }));
    fireEvent.change(screen.getByLabelText("Search your items"), { target: { value: "sony" } });
    expect(screen.queryByRole("article", { name: "boAt Airdopes 131" })).toBeNull();
    expect(card("Sony WH-1000XM5")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Search your items"), { target: { value: "iphone" } });
    expect(screen.getByText(/Nothing called "iphone" here/)).toBeTruthy();
  });

  it("checks every item, skipping one checked a moment ago", async () => {
    const second = makeItem({ id: 2, name: "Sony WH-1000XM5", listings: [makeListing({ id: 3, product_id: "B0B1" })] });
    const requests = fakeServer({
      "GET /api/items": () => [makeItem(), second],
      "POST /api/items/1/check": () => ({ item: makeItem(), alerts: [], errors: [] }),
      "POST /api/items/2/check": failWith(429, "Checked less than 5 minutes ago.", { "Retry-After": "120" }),
    });
    render(<App />);
    await screen.findByRole("article", { name: "Sony WH-1000XM5" });

    fireEvent.click(screen.getByRole("button", { name: "Check all" }));
    expect(await screen.findByText(/Checked 1 item. 1 item had just been checked, so we skipped it./)).toBeTruthy();
    expect(requests.filter((request) => request.key.startsWith("POST /api/items/")).map((request) => request.key)).toEqual([
      "POST /api/items/1/check",
      "POST /api/items/2/check",
    ]);
  });

  it("lists the alerts", async () => {
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "GET /api/alerts?limit=20": () => [
        {
          id: 1,
          item_id: 1,
          item_name: "boAt Airdopes 131",
          site: "amazon",
          kind: "big_drop",
          price: 899,
          message: "boAt Airdopes 131 is ₹899 on Amazon, 35% below its usual ₹1,399",
          url: AMAZON,
          created_at: now,
          sent_at: now,
        },
      ],
    });
    render(<App />);
    const alerts = await screen.findByRole("region", { name: /Alerts/ });
    expect(await within(alerts).findByText(/35% below its usual/)).toBeTruthy();
    expect(within(alerts).getByText("Big drop")).toBeTruthy();
    expect(within(alerts).getByText(/sent to Telegram/)).toBeTruthy();
  });
});

describe("an item's details", () => {
  it("checks prices now and shows a new alert", async () => {
    const message = "boAt Airdopes 131 is ₹999 on Amazon, at or below your ₹1,000 target";
    const cheaper = makeItem({ listings: [makeListing({ last_price: 999 })] });
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "POST /api/items/1/check": () => ({ item: cheaper, alerts: [message], errors: [] }),
    });
    render(<App />);

    const details = await openDetails();
    fireEvent.click(within(details).getByRole("button", { name: "Check now" }));
    expect(await within(details).findByText(/Target hit! ₹1,000 or less/)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(message);
  });

  it("says when to try again after a check a moment ago", async () => {
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "POST /api/items/1/check": failWith(
        429,
        "Checked less than 5 minutes ago. To go easy on the stores, try again in 4 minutes.",
        { "Retry-After": "240" },
      ),
    });
    render(<App />);

    const details = await openDetails();
    fireEvent.click(within(details).getByRole("button", { name: "Check now" }));
    expect((await within(details).findByRole("alert")).textContent).toContain("try again in 4 minutes");
  });

  it("shows the stores and what the history says", async () => {
    const both = makeItem({ listings: [makeListing(), flipkartListing()] });
    fakeServer({ "GET /api/items": () => [both] });
    render(<App />);

    const details = await openDetails();
    expect(within(details).getByText("Cheapest")).toBeTruthy();
    const facts = within(details).getByRole("region", { name: "Price facts" });
    expect(facts.textContent).toContain("₹1,199");     // lowest seen
    expect(facts.textContent).toContain("₹1,499");     // highest seen
    expect(within(details).getByRole("link", { name: /Open Flipkart/ }).getAttribute("href")).toBe(FLIPKART);
  });

  it("changes and removes the target, with suggestions", async () => {
    const requests = fakeServer({
      "GET /api/items": () => [makeItem()],
      "PATCH /api/items/1": (body) => makeItem({ target_price: (body as { target_price: number | null }).target_price }),
    });
    render(<App />);

    const details = await openDetails();
    const input = within(details).getByLabelText("Alert me when the price gets close to") as HTMLInputElement;
    fireEvent.click(within(details).getByRole("button", { name: "Lowest seen ₹1,199" }));
    expect(input.value).toBe("1199");

    fireEvent.change(input, { target: { value: "1,250" } });
    fireEvent.click(within(details).getByRole("button", { name: "Save target" }));
    expect(await within(details).findByText(/₹49 to go/)).toBeTruthy();
    expect(requests.at(-1)?.body).toEqual({ target_price: 1250 });

    fireEvent.click(within(details).getByRole("button", { name: "Remove target" }));
    expect(await within(details).findByText(/No target yet/)).toBeTruthy();
    expect(requests.at(-1)?.body).toEqual({ target_price: null });
  });

  it("asks before removing", async () => {
    const requests = fakeServer({ "GET /api/items": () => [makeItem()], "DELETE /api/items/1": () => undefined });
    render(<App />);

    const details = await openDetails();
    fireEvent.click(within(details).getByRole("button", { name: "Remove" }));
    expect(requests.some((request) => request.key === "DELETE /api/items/1")).toBe(false);
    fireEvent.click(within(details).getByRole("button", { name: "Yes, remove" }));
    expect(await screen.findByText("Nothing tracked yet")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("adds the other store's link", async () => {
    const both = makeItem({ listings: [makeListing(), flipkartListing()] });
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "POST /api/items/1/listings": () => ({ item: both, alerts: [], errors: [] }),
    });
    render(<App />);

    const details = await openDetails();
    fireEvent.change(within(details).getByLabelText("The same product on Flipkart"), { target: { value: FLIPKART } });
    fireEvent.click(within(details).getByRole("button", { name: "Add Flipkart" }));
    expect(await within(details).findByText("Cheapest")).toBeTruthy();
    expect(within(details).queryByLabelText("The same product on Flipkart")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Added Flipkart.");
  });

  it("closes with Escape", async () => {
    fakeServer({ "GET /api/items": () => [makeItem()] });
    render(<App />);
    await openDetails();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("draws the price history, with a table view", async () => {
    const both = makeItem({ listings: [makeListing(), flipkartListing()] });
    fakeServer({
      "GET /api/items": () => [both],
      "GET /api/items/1/history?days=30": () => [
        {
          listing_id: 1,
          site: "amazon",
          prices: [
            { checked_at: "2026-11-03T03:30:00Z", price: 1399, in_stock: true },
            { checked_at: "2026-11-04T03:30:00Z", price: null, in_stock: false },
            { checked_at: "2026-11-05T03:30:00Z", price: 1299, in_stock: true },
          ],
        },
        { listing_id: 2, site: "flipkart", prices: [{ checked_at: "2026-11-05T03:31:00Z", price: 1249, in_stock: true }] },
      ],
    });
    render(<App />);

    const details = await openDetails();
    const history = await within(details).findByRole("region", { name: /Price history/ });
    const chart = await within(history).findByRole("group", { name: /Price chart/ });
    expect(chart.querySelectorAll("path.price-line")).toHaveLength(2);
    expect(within(history).getByRole("list", { name: "Stores" }).textContent).toBe("AmazonFlipkart");
    expect(within(history).getByText(/Lowest in this period/).textContent).toContain("₹1,249 on Flipkart");

    fireEvent.keyDown(chart, { key: "End" });
    expect(chart.querySelector(".tooltip")?.textContent).toContain("₹1,249");

    fireEvent.click(within(history).getByRole("button", { name: "Show as table" }));
    const rows = within(history).getAllByRole("row");
    expect(rows).toHaveLength(5); // a header and four checks
    expect(rows[1].textContent).toContain("Flipkart");
    expect(within(history).getByText("Out of stock")).toBeTruthy();
  });
});
