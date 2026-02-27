import { test, expect, type Page } from "@playwright/test";

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`;
}

async function registerAndLogin(page: Page): Promise<void> {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Display Name").fill("Dashboard Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("testpassword123");
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/", { timeout: 10_000 });
}

test.describe("Dashboard", () => {
  test("shows empty state when no leagues", async ({ page }) => {
    await registerAndLogin(page);

    await expect(page.getByText("No leagues yet")).toBeVisible();
    await expect(
      page.getByText("Link a platform account and sync your leagues"),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Link Account" }),
    ).toBeVisible();
  });

  test("shows league cards when leagues exist", async ({ page }) => {
    await registerAndLogin(page);

    // Mock the leagues API to return data
    await page.route("**/api/leagues", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "00000000-0000-0000-0000-000000000001",
              name: "E2E Dynasty League",
              season: 2025,
              scoring_type: "ppr",
              roster_size: 15,
              platform_type: "sleeper",
              team_name: "My Team",
            },
            {
              id: "00000000-0000-0000-0000-000000000002",
              name: "E2E Redraft League",
              season: 2025,
              scoring_type: "half_ppr",
              roster_size: 10,
              platform_type: "sleeper",
              team_name: "Other Team",
            },
          ]),
        });
      } else {
        await route.continue();
      }
    });

    // Navigate to dashboard to trigger the mock
    await page.goto("/");
    await expect(page).toHaveURL("/", { timeout: 5_000 });

    // Should show "My Leagues" heading
    await expect(page.getByText("My Leagues")).toBeVisible({ timeout: 5_000 });

    // Should show league cards
    await expect(page.getByText("E2E Dynasty League")).toBeVisible();
    await expect(page.getByText("E2E Redraft League")).toBeVisible();
    await expect(page.getByText("PPR")).toBeVisible();
    await expect(page.getByText("My Team")).toBeVisible();
  });

  test("navigate to league detail from card", async ({ page }) => {
    await registerAndLogin(page);

    const leagueId = "00000000-0000-0000-0000-000000000001";

    // Mock leagues list
    await page.route("**/api/leagues", async (route) => {
      if (route.request().method() === "GET" && !route.request().url().includes(leagueId)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: leagueId,
              name: "Clickable League",
              season: 2025,
              scoring_type: "ppr",
              roster_size: 15,
              platform_type: "sleeper",
              team_name: "My Team",
            },
          ]),
        });
      } else {
        await route.continue();
      }
    });

    // Mock league detail
    await page.route(`**/api/leagues/${leagueId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: leagueId,
          name: "Clickable League",
          season: 2025,
          scoring_type: "ppr",
          roster_size: 15,
          platform_type: "sleeper",
          team_name: "My Team",
          standings: [],
          roster: [],
          recent_matchups: [],
          recent_transactions: [],
        }),
      });
    });

    await page.goto("/");
    await expect(page.getByText("Clickable League")).toBeVisible({
      timeout: 5_000,
    });

    // Click the league card
    await page.getByText("Clickable League").click();

    // Should navigate to league detail
    await expect(page).toHaveURL(`/leagues/${leagueId}`, { timeout: 5_000 });
    await expect(
      page.locator("h1").filter({ hasText: "Clickable League" }),
    ).toBeVisible();
  });

  test("sidebar navigation works", async ({ page }) => {
    await registerAndLogin(page);

    // Desktop sidebar should show nav items
    await expect(
      page.locator("aside").getByRole("link", { name: "Dashboard" }),
    ).toBeVisible();
    await expect(
      page.locator("aside").getByRole("link", { name: "Link Accounts" }),
    ).toBeVisible();

    // Navigate to link accounts via sidebar
    await page
      .locator("aside")
      .getByRole("link", { name: "Link Accounts" })
      .click();
    await expect(page).toHaveURL("/link-accounts");

    // Navigate back to dashboard via sidebar
    await page
      .locator("aside")
      .getByRole("link", { name: "Dashboard" })
      .click();
    await expect(page).toHaveURL("/");
  });

  test("header shows user display name and logout", async ({ page }) => {
    await registerAndLogin(page);

    // Header should have display name and logout
    await expect(page.getByText("Dashboard Tester")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Logout" }),
    ).toBeVisible();
  });
});
