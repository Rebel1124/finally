import { expect, test } from "@playwright/test";
import { rowForTicker, watchlistAddForm, watchlistTable } from "./helpers";

test("add and remove a ticker from the watchlist", async ({ page }) => {
  await page.goto("/");

  const table = watchlistTable(page);
  const form = watchlistAddForm(page);

  await form.getByPlaceholder("Ticker").fill("PYPL");
  await form.getByRole("button", { name: "Add" }).click();

  const row = rowForTicker(page, table, "PYPL");
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "Remove PYPL" }).click();
  await expect(row).toHaveCount(0);
});
