import { expect, test } from "@playwright/test";

const GITHUB_URL = "https://github.com/AbdullahBera/hermes-sidekick";

test.beforeEach(async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("renders the approved content and safe GitHub links", async ({ page }) => {
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your own private AI sidekick.");
  await expect(page.getByText(/Connect Gmail, Calendar, and Signal/)).toBeVisible();
  await expect(page.getByText("Plug in what you use. Turn on what you need. Sidekick handles the rest.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hermes Sidekick" })).toBeVisible();
  await expect(page.getByText("Running privately")).toBeVisible();
  await expect(page.getByText("Connect your apps")).toBeVisible();
  await expect(page.getByText("Choose your routines")).toBeVisible();
  await expect(page.getByText("Stay private")).toBeVisible();
  await expect(page.getByText(/Six messages sorted/)).toBeVisible();
  await expect(page.getByText(/Reply to Maya — 3 days/)).toBeVisible();
  await expect(page.getByText(/Draft a reply\? ✍️/)).toBeVisible();

  const githubLinks = page.locator(`a[href="${GITHUB_URL}"]`);
  await expect(githubLinks).toHaveCount(2);

  for (const link of await githubLinks.all()) {
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", /noopener/);
    await expect(link).toHaveAttribute("rel", /noreferrer/);
  }
});

test("supports keyboard focus and has no horizontal overflow", async ({ page }) => {
  const cta = page.getByRole("link", { name: /View Hermes Sidekick on GitHub/ }).last();
  await cta.focus();
  await expect(cta).toBeFocused();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("captures the verified viewport", async ({ page }, testInfo) => {
  await page.screenshot({
    path: testInfo.outputPath(`landing-${testInfo.project.name}.png`),
    fullPage: true,
  });
});
