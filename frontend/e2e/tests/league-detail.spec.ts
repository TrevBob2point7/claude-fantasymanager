import { test, expect, type Page } from "@playwright/test";

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`;
}

const LEAGUE_ID = "00000000-0000-0000-0000-000000000099";

const leagueDetail = {
  id: LEAGUE_ID,
  name: "Test Detail League",
  season: 2025,
  scoring_type: "ppr",
  roster_size: 15,
  platform_type: "sleeper",
  team_name: "My Dynasty Team",
  roster: [
    {
      id: "p1",
      player_name: "Patrick Mahomes",
      position: "QB",
      team: "KC",
      slot: "STARTER",
    },
    {
      id: "p2",
      player_name: "Derrick Henry",
      position: "RB",
      team: "BAL",
      slot: "STARTER",
    },
    {
      id: "p3",
      player_name: "Ja'Marr Chase",
      position: "WR",
      team: "CIN",
      slot: null,
    },
  ],
  standings: [
    {
      id: "s1",
      team_name: "My Dynasty Team",
      rank: 1,
      wins: 10,
      losses: 3,
      ties: 0,
      points_for: 1850.5,
      points_against: 1620.3,
    },
    {
      id: "s2",
      team_name: "Rival Team",
      rank: 2,
      wins: 9,
      losses: 4,
      ties: 0,
      points_for: 1790.2,
      points_against: 1680.1,
    },
  ],
  recent_matchups: [
    {
      id: "m1",
      week: 13,
      home_team_name: "My Dynasty Team",
      away_team_name: "Rival Team",
      home_score: 142.5,
      away_score: 128.3,
    },
    {
      id: "m2",
      week: 12,
      home_team_name: "Rival Team",
      away_team_name: "My Dynasty Team",
      home_score: 115.0,
      away_score: 130.7,
    },
  ],
  recent_transactions: [
    {
      id: "t1",
      type: "add",
      player_name: "Keenan Allen",
      from_team_name: null,
      to_team_name: "My Dynasty Team",
      timestamp: "2025-11-15T12:00:00Z",
    },
    {
      id: "t2",
      type: "drop",
      player_name: "Zay Flowers",
      from_team_name: "My Dynasty Team",
      to_team_name: null,
      timestamp: "2025-11-14T12:00:00Z",
    },
    {
      id: "t3",
      type: "trade",
      player_name: "Travis Kelce",
      from_team_name: "Rival Team",
      to_team_name: "My Dynasty Team",
      timestamp: "2025-11-10T12:00:00Z",
    },
  ],
};

async function setupAuthAndMocks(page: Page): Promise<void> {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Display Name").fill("Detail Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("testpassword123");
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/", { timeout: 10_000 });

  // Mock the league detail endpoint
  await page.route(`**/api/leagues/${LEAGUE_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(leagueDetail),
    });
  });
}

test.describe("League Detail", () => {
  test("displays league header info", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    await expect(
      page.locator("h1").filter({ hasText: "Test Detail League" }),
    ).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("PPR")).toBeVisible();
    await expect(page.getByText("My Dynasty Team")).toBeVisible();
    await expect(page.getByText("15 roster spots")).toBeVisible();
  });

  test("back to dashboard link works", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    await expect(page.getByText("Back to Dashboard")).toBeVisible({
      timeout: 5_000,
    });
    await page.getByText("Back to Dashboard").click();
    await expect(page).toHaveURL("/");
  });

  test("roster tab shows player table", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    // Roster tab should be active by default
    await expect(page.getByText("Patrick Mahomes")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText("Derrick Henry")).toBeVisible();
    await expect(page.getByText("Ja'Marr Chase")).toBeVisible();

    // Table headers
    await expect(page.getByText("Player")).toBeVisible();
    await expect(page.getByText("Pos")).toBeVisible();
    await expect(page.getByText("Team")).toBeVisible();
    await expect(page.getByText("Slot")).toBeVisible();

    // Position and team data
    await expect(page.getByText("QB")).toBeVisible();
    await expect(page.getByText("KC")).toBeVisible();
  });

  test("standings tab shows rankings", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    // Click standings tab
    await page.getByRole("button", { name: "Standings" }).click();

    // Should show standings table
    await expect(page.getByText("Rank")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("cell", { name: "My Dynasty Team" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Rival Team" })).toBeVisible();

    // Check W/L columns
    await expect(page.getByRole("columnheader", { name: "W" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "L" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "PF" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "PA" })).toBeVisible();
  });

  test("matchups tab shows weekly matchups", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    // Click matchups tab
    await page.getByRole("button", { name: "Matchups" }).click();

    // Should show matchup cards
    await expect(page.getByText("Week 13")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Week 12")).toBeVisible();
    await expect(page.getByText("142.5")).toBeVisible();
    await expect(page.getByText("128.3")).toBeVisible();
    // "vs" separator
    await expect(page.getByText("vs").first()).toBeVisible();
  });

  test("transactions tab shows transaction feed", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    // Click transactions tab
    await page.getByRole("button", { name: "Transactions" }).click();

    // Should show transaction entries
    await expect(page.getByText("Keenan Allen")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText("Zay Flowers")).toBeVisible();
    await expect(page.getByText("Travis Kelce")).toBeVisible();

    // Transaction type labels
    await expect(page.getByText("add").first()).toBeVisible();
    await expect(page.getByText("drop")).toBeVisible();
    await expect(page.getByText("trade")).toBeVisible();
  });

  test("switching between all tabs", async ({ page }) => {
    await setupAuthAndMocks(page);
    await page.goto(`/leagues/${LEAGUE_ID}`);

    // Start on roster (default)
    await expect(page.getByText("Patrick Mahomes")).toBeVisible({
      timeout: 5_000,
    });

    // Switch to standings
    await page.getByRole("button", { name: "Standings" }).click();
    await expect(page.getByRole("cell", { name: "My Dynasty Team" })).toBeVisible();

    // Switch to matchups
    await page.getByRole("button", { name: "Matchups" }).click();
    await expect(page.getByText("Week 13")).toBeVisible();

    // Switch to transactions
    await page.getByRole("button", { name: "Transactions" }).click();
    await expect(page.getByText("Keenan Allen")).toBeVisible();

    // Switch back to roster
    await page.getByRole("button", { name: "Roster" }).click();
    await expect(page.getByText("Patrick Mahomes")).toBeVisible();
  });
});
