import { expect, test } from "@playwright/test";
import { formatCurrency, headerFigure, positionsTable, rowForTicker, tradeBar } from "./helpers";

test.describe.configure({ mode: "serial" });

test.describe("trading", () => {
  test("buying shares decreases cash and creates a position", async ({ page, request }) => {
    await page.goto("/");

    const bar = tradeBar(page);
    await bar.getByPlaceholder("Ticker").fill("AAPL");
    await bar.getByPlaceholder("Qty").fill("2");
    await bar.getByRole("button", { name: "Buy", exact: true }).click();

    const positions = positionsTable(page);
    const row = rowForTicker(page, positions, "AAPL");
    await expect(row).toBeVisible();
    await expect(row.getByRole("cell", { name: "2", exact: true })).toBeVisible();

    const portfolio = await (await request.get("/api/portfolio")).json();
    expect(portfolio.cash_balance).toBeLessThan(10000);
    await expect(page.getByText(formatCurrency(portfolio.cash_balance))).toBeVisible();

    // total_value drifts continuously with the live simulated price, so it can't be
    // compared exactly against a separately-fetched API snapshot; just confirm the
    // header renders an updated, well-formed figure.
    const totalValueText = await headerFigure(page, "Portfolio Value");
    expect(totalValueText).toMatch(/^\$[\d,]+\.\d{2}$/);
  });

  test("selling part of a position reduces quantity and increases cash", async ({
    page,
    request,
  }) => {
    await page.goto("/");
    const before = await (await request.get("/api/portfolio")).json();

    const bar = tradeBar(page);
    await bar.getByPlaceholder("Ticker").fill("AAPL");
    await bar.getByPlaceholder("Qty").fill("1");
    await bar.getByRole("button", { name: "Sell", exact: true }).click();

    const positions = positionsTable(page);
    const row = rowForTicker(page, positions, "AAPL");
    await expect(row).toBeVisible();
    await expect(row.getByRole("cell", { name: "1", exact: true })).toBeVisible();

    const after = await (await request.get("/api/portfolio")).json();
    expect(after.cash_balance).toBeGreaterThan(before.cash_balance);
  });

  test("selling the remaining shares removes the position", async ({ page, request }) => {
    await page.goto("/");

    const bar = tradeBar(page);
    await bar.getByPlaceholder("Ticker").fill("AAPL");
    await bar.getByPlaceholder("Qty").fill("1");
    await bar.getByRole("button", { name: "Sell", exact: true }).click();

    const positions = positionsTable(page);
    await expect(rowForTicker(page, positions, "AAPL")).toHaveCount(0);
    await expect(positions.getByText("No positions yet")).toBeVisible();

    const after = await (await request.get("/api/portfolio")).json();
    expect(
      after.positions.find((p: { ticker: string }) => p.ticker === "AAPL"),
    ).toBeUndefined();
  });
});
