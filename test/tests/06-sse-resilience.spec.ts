import { expect, test } from "@playwright/test";
import { connectionLabel } from "./helpers";

test("connection indicator shows connected during normal operation", async ({ page }) => {
  await page.goto("/");
  await expect(connectionLabel(page)).toHaveText("Connected", { timeout: 15000 });
});

test("connection indicator recovers once the price stream becomes reachable", async ({
  page,
  context,
}) => {
  // Playwright's context.setOffline() does not sever an already-open EventSource
  // stream (only new requests are blocked), so a genuine "connected -> dropped ->
  // reconnected" transition isn't reliably reproducible here. Instead this blocks the
  // stream before the first connection attempt and then unblocks it, exercising the
  // same client-side reconnect path (EventSource.onerror -> "reconnecting"/"connecting"
  // -> onopen -> "open") that a mid-stream drop would trigger.
  let blockStream = true;
  await context.route("**/api/stream/prices", (route) =>
    blockStream ? route.abort() : route.continue(),
  );

  await page.goto("/");
  await expect(connectionLabel(page)).toHaveText(/Connecting|Reconnecting/, { timeout: 5000 });

  blockStream = false;
  await expect(connectionLabel(page)).toHaveText("Connected", { timeout: 15000 });
});
