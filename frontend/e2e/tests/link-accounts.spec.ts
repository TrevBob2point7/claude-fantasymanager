import { test, expect, type Page } from "@playwright/test";

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`;
}

async function registerAndLogin(page: Page): Promise<void> {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Display Name").fill("Link Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("testpassword123");
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/", { timeout: 10_000 });
}

test.describe("Link Accounts", () => {
  test("navigate to link accounts page", async ({ page }) => {
    await registerAndLogin(page);

    // Click the "Link Account" link from empty dashboard
    await page.getByRole("link", { name: "Link Account" }).click();
    await expect(page).toHaveURL("/link-accounts");
    await expect(page.getByText("Link Accounts")).toBeVisible();
    await expect(page.getByText("Link Sleeper Account")).toBeVisible();
  });

  test("link a sleeper account", async ({ page }) => {
    await registerAndLogin(page);
    await page.goto("/link-accounts");

    // Fill in the username and submit
    await page
      .getByPlaceholder("Sleeper username")
      .fill("testsleeperuser");
    await page.getByRole("button", { name: "Link" }).click();

    // Should show the linked account
    await expect(page.getByText("testsleeperuser")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText("sleeper")).toBeVisible();

    // Action buttons should appear
    await expect(page.getByRole("button", { name: "Discover" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sync" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();
  });

  test("remove a linked account", async ({ page }) => {
    await registerAndLogin(page);
    await page.goto("/link-accounts");

    // Link an account first
    await page.getByPlaceholder("Sleeper username").fill("to-remove");
    await page.getByRole("button", { name: "Link" }).click();
    await expect(page.getByText("to-remove")).toBeVisible({ timeout: 5_000 });

    // Remove it
    await page.getByRole("button", { name: "Remove" }).click();
    // Account should disappear
    await expect(page.getByText("to-remove")).not.toBeVisible({
      timeout: 5_000,
    });
  });

  test("discover leagues for linked account", async ({ page }) => {
    await registerAndLogin(page);
    await page.goto("/link-accounts");

    // Link an account
    await page.getByPlaceholder("Sleeper username").fill("discoveruser");
    await page.getByRole("button", { name: "Link" }).click();
    await expect(page.getByText("discoveruser")).toBeVisible({
      timeout: 5_000,
    });

    // Mock the discover API response
    await page.route("**/api/leagues/discover", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            platform_league_id: "lg-e2e-1",
            name: "E2E Dynasty League",
            season: 2025,
            scoring_type: "ppr",
            roster_size: 15,
            already_linked: false,
          },
          {
            platform_league_id: "lg-e2e-2",
            name: "E2E Redraft League",
            season: 2025,
            scoring_type: "half_ppr",
            roster_size: 10,
            already_linked: true,
          },
        ]),
      });
    });

    // Click Discover
    await page.getByRole("button", { name: "Discover" }).click();

    // Should show discovered leagues
    await expect(page.getByText("Discovered Leagues")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText("E2E Dynasty League")).toBeVisible();
    await expect(page.getByText("E2E Redraft League")).toBeVisible();

    // Already linked league should show "Linked" badge
    await expect(page.getByText("Linked")).toBeVisible();
  });
});
