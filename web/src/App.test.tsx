import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { Item } from "./api";

const AMAZON = "https://www.amazon.in/dp/B0D3DK779N";
const FLIPKART = "https://www.flipkart.com/boat-airdopes-131/p/itma0ea2cce3d648?pid=ACCHDYCG92CUSJFT";
const now = new Date().toISOString();

function makeItem(changes: Partial<Item> = {}): Item {
  return {
    id: 1,
    name: "boAt Airdopes 131",
    target_price: 1000,
    active: true,
    created_at: now,
    listings: [
      {
        id: 1,
        site: "amazon",
        product_id: "B0D3DK779N",
        url: AMAZON,
        title: "boAt Airdopes 131",
        last_price: 1299,
        last_in_stock: true,
        last_checked_at: now,
        last_error: null,
      },
    ],
    ...changes,
  };
}

type Route = (body: unknown) => unknown;

/** Answer fetch() from `routes`, keyed "METHOD /api/path". Returns the requests made. */
function fakeServer(routes: Record<string, Route>) {
  const requests: { key: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url}`;
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ key, body });
      const answer = routes[key] ? routes[key](body) : new Response(null, { status: 404 });
      if (answer instanceof Response) return answer;
      return new Response(answer === undefined ? null : JSON.stringify(answer), { status: answer === undefined ? 204 : 200 });
    }),
  );
  return requests;
}

const failWith = (status: number, detail: string) => () => new Response(JSON.stringify({ detail }), { status });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the page", () => {
  it("shows each item's price and how far it is from the target", async () => {
    fakeServer({ "GET /api/items": () => [makeItem()], "GET /api/alerts?limit=20": () => [] });
    render(<App />);

    expect(await screen.findByText("boAt Airdopes 131")).toBeTruthy();
    expect(screen.getByText("₹1,299")).toBeTruthy();
    expect(screen.getByText(/₹299 above your ₹1,000 target/)).toBeTruthy();
    expect(screen.getByText("Checked just now")).toBeTruthy();
    expect(screen.getByText(/No alerts yet/)).toBeTruthy();
  });

  it("explains how to start when nothing is tracked", async () => {
    fakeServer({ "GET /api/items": () => [], "GET /api/alerts?limit=20": () => [] });
    render(<App />);
    expect(await screen.findByText("Nothing tracked yet")).toBeTruthy();
  });

  it("says when the server isn't running", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain("python -m price_tracker serve");
  });

  it("starts tracking a pasted link", async () => {
    const requests = fakeServer({
      "GET /api/items": () => [],
      "GET /api/alerts?limit=20": () => [],
      "POST /api/items": () => ({ item: makeItem(), alerts: [], errors: [] }),
    });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: `Check this out ${AMAZON}` } });
    fireEvent.change(screen.getByLabelText(/Alert me at/), { target: { value: "1,000" } });
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));

    expect(await screen.findByText("boAt Airdopes 131")).toBeTruthy();
    expect(requests.find((request) => request.key === "POST /api/items")?.body).toEqual({
      link: `Check this out ${AMAZON}`,
      target_price: 1000,
    });
    expect(screen.getByRole("status").textContent).toContain("Now tracking boAt Airdopes 131. ₹1,299 on Amazon.");
  });

  it("shows why a link couldn't be added", async () => {
    fakeServer({
      "GET /api/items": () => [],
      "GET /api/alerts?limit=20": () => [],
      "POST /api/items": failWith(422, "Only links from amazon.in, flipkart.com are supported, got: example.com"),
    });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: "https://example.com/x" } });
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Only links from amazon.in");
  });

  it("refuses a target that isn't a price before asking the server", async () => {
    const requests = fakeServer({ "GET /api/items": () => [], "GET /api/alerts?limit=20": () => [] });
    render(<App />);
    await screen.findByText("Nothing tracked yet");

    fireEvent.change(screen.getByLabelText("Product link"), { target: { value: AMAZON } });
    fireEvent.change(screen.getByLabelText(/Alert me at/), { target: { value: "cheap" } });
    fireEvent.click(screen.getByRole("button", { name: "Start tracking" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Write the target price as a number");
    expect(requests.some((request) => request.key === "POST /api/items")).toBe(false);
  });
});

describe("an item", () => {
  it("checks prices now and shows a new alert", async () => {
    const message = "boAt Airdopes 131 is ₹999 on Amazon, at or below your ₹1,000 target";
    const cheaper = makeItem({ listings: [{ ...makeItem().listings[0], last_price: 999 }] });
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "GET /api/alerts?limit=20": () => [],
      "POST /api/items/1/check": () => ({ item: cheaper, alerts: [message], errors: [] }),
    });
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Check now" }));
    expect(await screen.findByText("₹999")).toBeTruthy();
    expect(screen.getByText(/At or below your ₹1,000 target/)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(message);
  });

  it("changes and removes the target", async () => {
    const requests = fakeServer({
      "GET /api/items": () => [makeItem()],
      "GET /api/alerts?limit=20": () => [],
      "PATCH /api/items/1": (body) => makeItem({ target_price: (body as { target_price: number | null }).target_price }),
    });
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Change target" }));
    const input = screen.getByLabelText("Alert me when the price gets close to");
    fireEvent.change(input, { target: { value: "1,250" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/₹49 above your ₹1,250 target/)).toBeTruthy();
    expect(requests.at(-1)?.body).toEqual({ target_price: 1250 });

    fireEvent.click(screen.getByRole("button", { name: "Change target" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove target" }));
    expect(await screen.findByText(/No target yet/)).toBeTruthy();
    expect(requests.at(-1)?.body).toEqual({ target_price: null });
  });

  it("asks before removing", async () => {
    const requests = fakeServer({
      "GET /api/items": () => [makeItem()],
      "GET /api/alerts?limit=20": () => [],
      "DELETE /api/items/1": () => undefined,
    });
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    expect(requests.some((request) => request.key === "DELETE /api/items/1")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Yes, remove" }));
    expect(await screen.findByText("Nothing tracked yet")).toBeTruthy();
  });

  it("adds the other store's link", async () => {
    const both = makeItem({
      listings: [
        makeItem().listings[0],
        { ...makeItem().listings[0], id: 2, site: "flipkart", url: FLIPKART, last_price: 1249 },
      ],
    });
    fakeServer({
      "GET /api/items": () => [makeItem()],
      "GET /api/alerts?limit=20": () => [],
      "POST /api/items/1/listings": () => ({ item: both, alerts: [], errors: [] }),
    });
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Add Flipkart link" }));
    fireEvent.change(screen.getByLabelText("The same product on Flipkart"), { target: { value: FLIPKART } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByText("₹1,249")).toBeTruthy();
    expect(screen.getByText("Lowest")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Add .* link/ })).toBeNull();
  });

  it("draws the price history, with a table view", async () => {
    const item = makeItem({
      listings: [
        makeItem().listings[0],
        { ...makeItem().listings[0], id: 2, site: "flipkart", url: FLIPKART, last_price: 1249 },
      ],
    });
    fakeServer({
      "GET /api/items": () => [item],
      "GET /api/alerts?limit=20": () => [],
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

    fireEvent.click(await screen.findByRole("button", { name: "Price history" }));
    const history = await screen.findByRole("region", { name: /Price history/ });
    const chart = await within(history).findByRole("group", { name: /Price chart/ });
    expect(chart.querySelectorAll("path.price-line")).toHaveLength(2);
    expect(within(history).getByRole("list", { name: "Stores" }).textContent).toBe("AmazonFlipkart");
    expect(within(history).getByText(/Lowest in this period/).textContent).toContain("₹1,249 on Flipkart");

    fireEvent.keyDown(chart, { key: "End" });
    expect(chart.querySelector(".tooltip")?.textContent).toContain("₹1,249");

    fireEvent.click(within(history).getByRole("button", { name: "Show as table" }));
    const rows = within(history).getAllByRole("row");
    expect(rows).toHaveLength(5);       // a header and four checks
    expect(rows[1].textContent).toContain("Flipkart");
    expect(within(history).getByText("Out of stock")).toBeTruthy();
  });
});
