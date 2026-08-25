import { expect, test } from "@playwright/test";
import { panelFor, positionsTable, rowForTicker, tradeBar } from "./helpers";

test("portfolio heatmap and P&L chart render after trades", async ({ page, request }) => {
  await page.goto("/");

  // two trades so at least two portfolio snapshots exist (the P&L chart needs >= 2
  // points to render a line instead of its "not enough history" placeholder) and a
  // position stays open (so the heatmap has a cell to draw).
  const bar = tradeBar(page);
  await bar.getByPlaceholder("Ticker").fill("MSFT");
  await bar.getByPlaceholder("Qty").fill("2");
  await bar.getByRole("button", { name: "Buy", exact: true }).click();

  const positions = positionsTable(page);
  await expect(rowForTicker(page, positions, "MSFT")).toBeVisible();

  await bar.getByPlaceholder("Ticker").fill("MSFT");
  await bar.getByPlaceholder("Qty").fill("1");
  await bar.getByRole("button", { name: "Sell", exact: true }).click();
  await expect(rowForTicker(page, positions, "MSFT")).toBeVisible();

  const history = await (await request.get("/api/portfolio/history")).json();
  expect(history.length).toBeGreaterThanOrEqual(2);

  const heatmapPanel = panelFor(page, "Portfolio Heatmap");
  await expect(heatmapPanel.locator("svg rect").first()).toBeVisible();

  const pnlPanel = panelFor(page, "Portfolio Value");
  await expect(pnlPanel.getByText("Not enough history yet")).toHaveCount(0);
  await expect(pnlPanel.locator("svg path").first()).toBeVisible();
});
