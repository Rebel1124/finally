import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, connectionLabel, watchlistTable } from "./helpers";

test("fresh start shows default watchlist, starting cash, and live prices", async ({ page }) => {
  await page.goto("/");

  const table = watchlistTable(page);
  await expect(table).toBeVisible();
  await expect(table.locator("tbody tr")).toHaveCount(DEFAULT_TICKERS.length);

  for (const ticker of DEFAULT_TICKERS) {
    await expect(table.getByRole("cell", { name: ticker, exact: true })).toBeVisible();
  }

  // starting cash balance and portfolio total both read $10,000.00
  await expect(page.getByText("$10,000.00")).toHaveCount(2);

  await expect(connectionLabel(page)).toHaveText("Connected", { timeout: 15000 });

  // at least one live price tick has arrived via SSE (price cell is no longer the "—" placeholder)
  const firstPriceCell = table.locator("tbody tr").first().locator("td").nth(1);
  await expect(firstPriceCell).not.toHaveText("—", { timeout: 5000 });
});
