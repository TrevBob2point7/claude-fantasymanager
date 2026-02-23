import { expect, test } from "@playwright/test";

test("page loads and shows backend health status", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Fantasy Manager");
  await expect(page.locator("text=Backend: healthy")).toBeVisible({
    timeout: 15_000,
  });
});
