import { expect, test } from "@playwright/test";
import { positionsTable, rowForTicker } from "./helpers";

test("mocked AI chat executes a trade and shows an inline confirmation", async ({
  page,
  request,
}) => {
  await page.goto("/");

  const before = await (await request.get("/api/portfolio")).json();
  const beforeQty =
    before.positions.find((p: { ticker: string }) => p.ticker === "GOOGL")?.quantity ?? 0;

  await page.getByPlaceholder("Ask FinAlly…").fill("buy 3 GOOGL");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Mock: buying 3 GOOGL.")).toBeVisible();
  await expect(page.getByText(/Bought 3 GOOGL/)).toBeVisible();

  const positions = positionsTable(page);
  await expect(rowForTicker(page, positions, "GOOGL")).toBeVisible();

  const after = await (await request.get("/api/portfolio")).json();
  const afterQty =
    after.positions.find((p: { ticker: string }) => p.ticker === "GOOGL")?.quantity ?? 0;
  expect(afterQty).toBe(beforeQty + 3);
});
