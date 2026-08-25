import type { Locator, Page } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

export function formatCurrency(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function watchlistTable(page: Page): Locator {
  return page.locator("table").filter({ hasText: "Chg %" });
}

export function positionsTable(page: Page): Locator {
  return page.locator("table").filter({ hasText: "Avg Cost" });
}

export function watchlistAddForm(page: Page): Locator {
  return page.locator("form").filter({ has: page.getByRole("button", { name: "Add" }) });
}

export function tradeBar(page: Page): Locator {
  return page.locator('input[placeholder="Qty"]').locator("xpath=..");
}

// Text of the value div under a Header stat label (e.g. "Portfolio Value", "Cash").
export async function headerFigure(page: Page, label: string): Promise<string> {
  const labelDiv = page.locator("header div").filter({ hasText: new RegExp(`^${label}$`) });
  return (await labelDiv.locator("xpath=following-sibling::div[1]").innerText()).trim();
}

export function connectionLabel(page: Page): Locator {
  return page.locator("header").getByText(/^(Connected|Reconnecting|Connecting)$/);
}

export function rowForTicker(page: Page, table: Locator, ticker: string): Locator {
  return table.locator("tbody tr").filter({
    has: page.getByRole("cell", { name: ticker, exact: true }),
  });
}

// Nearest ancestor "flex-col" panel div for a given <h2> heading, matching the
// PortfolioHeatmap/PnLChart component root (`<div className="flex h-full flex-col">`).
export function panelFor(page: Page, headingName: string): Locator {
  return page
    .getByRole("heading", { name: headingName, exact: true })
    .locator("xpath=ancestor::div[contains(@class,'flex-col')][1]");
}
