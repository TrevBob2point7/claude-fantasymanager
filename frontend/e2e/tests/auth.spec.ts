import { test, expect } from "@playwright/test";

// Generate unique email per test run to avoid conflicts
function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`;
}

test.describe("Auth Flow", () => {
  test("register a new user and land on dashboard", async ({ page }) => {
    const email = uniqueEmail();

    await page.goto("/register");
    await expect(page.locator("h2")).toHaveText("Create Account");

    await page.getByLabel("Display Name").fill("E2E Tester");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("testpassword123");
    await page.getByRole("button", { name: "Create Account" }).click();

    // Should redirect to dashboard after successful registration
    await expect(page).toHaveURL("/", { timeout: 10_000 });
    await expect(page.getByText("No leagues yet")).toBeVisible();
  });

  test("login with registered user", async ({ page }) => {
    const email = uniqueEmail();

    // Register first
    await page.goto("/register");
    await page.getByLabel("Display Name").fill("Login Tester");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("testpassword123");
    await page.getByRole("button", { name: "Create Account" }).click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });

    // Logout
    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL("/login");

    // Login again
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("testpassword123");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page).toHaveURL("/", { timeout: 10_000 });
    await expect(page.getByText("No leagues yet")).toBeVisible();
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email").fill("nobody@example.com");
    await page.getByLabel("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(
      page.locator("text=Invalid email or password"),
    ).toBeVisible({ timeout: 5_000 });
    // Should stay on login page
    await expect(page).toHaveURL("/login");
  });

  test("logout redirects to login", async ({ page }) => {
    const email = uniqueEmail();

    // Register and land on dashboard
    await page.goto("/register");
    await page.getByLabel("Display Name").fill("Logout Tester");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("testpassword123");
    await page.getByRole("button", { name: "Create Account" }).click();
    await expect(page).toHaveURL("/", { timeout: 10_000 });

    // Logout
    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL("/login");

    // Trying to navigate to dashboard should redirect to login
    await page.goto("/");
    await expect(page).toHaveURL("/login", { timeout: 5_000 });
  });

  test("navigate between login and register", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h2")).toHaveText("Sign In");

    await page.getByRole("link", { name: "Register" }).click();
    await expect(page).toHaveURL("/register");
    await expect(page.locator("h2")).toHaveText("Create Account");

    await page.getByRole("link", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/login");
    await expect(page.locator("h2")).toHaveText("Sign In");
  });

  test("unauthenticated access redirects to login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL("/login", { timeout: 5_000 });
  });
});
