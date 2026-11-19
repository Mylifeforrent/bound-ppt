import { expect, test } from "@playwright/test";

test("six-stage deck generation with real PPTX export", async ({ page }) => {
  test.setTimeout(240_000);
  const shots = "/tmp/bound-ppt-e2e";
  const shot = async (name: string) => {
    await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true }).catch(() => undefined);
  };

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Start a deck" })).toBeVisible();

  await page.getByPlaceholder("What should the deck be about?").fill("Dify company introduction");
  await page
    .getByPlaceholder("Paste notes, a product brief, or any source text…")
    .fill(
      "Dify is an open-source LLM application development platform. " +
        "It combines visual workflow building, retrieval augmented generation, and agent orchestration. " +
        "Teams use it to ship internal copilots and customer-facing assistants. " +
        "Deployment options include cloud, self-hosted Docker, and Kubernetes. " +
        "The strategy emphasizes developer experience, plugin extensibility, and enterprise governance.",
    );
  await page.getByRole("button", { name: "Add text" }).click();
  await expect(page.getByText("Pasted text", { exact: true }).first()).toBeVisible();

  const accept = page.getByRole("button", { name: "Accept data notice" });
  if (await accept.isVisible().catch(() => false)) {
    await accept.click();
    await expect(page.getByText(/Data notice accepted/)).toBeVisible();
  }

  await page.getByRole("button", { name: /Start generating/ }).click();
  await expect(page).toHaveURL(/\/research$/, { timeout: 60_000 });
  await shot("01-research");

  const confirmGaps = page.getByRole("button", { name: "Confirm gaps" });
  await expect(confirmGaps).toBeVisible({ timeout: 60_000 });
  await confirmGaps.click();
  await expect(page.getByText(/Recording decision|Web search|No web supplements/).first()).toBeVisible();

  // Four sequential questions: only one radio group is interactive at a time.
  // Wait for each answer to be recorded before clicking the next question.
  for (let index = 0; index < 4; index += 1) {
    const recorded = page.getByText(/^Recorded:/);
    await expect(recorded).toHaveCount(index, { timeout: 30_000 });
    const radio = page.getByRole("radio", { checked: false }).first();
    await expect(radio).toBeVisible({ timeout: 30_000 });
    await radio.click();
    await expect(recorded).toHaveCount(index + 1, { timeout: 30_000 });
  }

  const generateProfile = page.getByRole("button", { name: "Generate profile" });
  await expect(generateProfile).toBeEnabled({ timeout: 30_000 });
  await generateProfile.click();
  await expect(page.getByText(/Content strategy|content strategy/)).toBeVisible({ timeout: 60_000 });
  await shot("02-profile");

  const generateOutline = page.getByRole("button", { name: "Generate outline" });
  await expect(generateOutline).toBeEnabled({ timeout: 60_000 });
  await generateOutline.click();
  await expect(page).toHaveURL(/\/outline$/, { timeout: 90_000 });
  await expect(page.getByText(/pages · .*sections/)).toBeVisible({ timeout: 60_000 });
  await shot("03-outline");

  const confirmOutline = page.getByRole("button", { name: /Confirm and continue now|Outline looks good, generate plan draft|Open plan draft/ });
  await confirmOutline.waitFor({ state: "visible", timeout: 30_000 });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (page.url().endsWith("/plan")) break;
    if (await confirmOutline.isVisible().catch(() => false) && (await confirmOutline.isEnabled().catch(() => false))) {
      await confirmOutline.click().catch(() => undefined);
    }
    await page.waitForTimeout(2_000);
  }
  await expect(page).toHaveURL(/\/(plan|style)$/, { timeout: 60_000 });
  await shot("04-plan");

  if (page.url().endsWith("/plan")) {
    const confirmPlan = page.getByRole("button", { name: "Confirm plan draft, choose style" });
    await Promise.race([
      page.waitForURL(/\/style$/, { timeout: 120_000 }),
      (async () => {
        await expect(confirmPlan).toBeEnabled({ timeout: 120_000 });
        await confirmPlan.click();
      })(),
    ]);
  }
  await expect(page).toHaveURL(/\/style$/, { timeout: 60_000 });
  await expect(page.getByText(/Style selection/).first()).toBeVisible();
  await shot("05-style");

  await page.getByRole("radio").first().click();
  const confirmStyle = page.getByRole("button", { name: "Confirm style and open design draft" });
  await expect(confirmStyle).toBeEnabled({ timeout: 30_000 });
  await confirmStyle.click();
  await expect(page).toHaveURL(/\/design$/, { timeout: 60_000 });

  await expect(page.getByText(/All pages have a current design/)).toBeVisible({ timeout: 180_000 });
  await shot("06-design");

  // Per-page variant history and undo (FR-6.4/FR-6.5).
  await page.getByRole("button", { name: /Page 3 of \d+:/ }).click();
  await expect(page.getByRole("button", { name: "Regenerate" })).toBeEnabled();
  await page.getByRole("button", { name: "Regenerate" }).click();
  await expect(page.getByText("1 version", { exact: true }).first()).toBeVisible({ timeout: 120_000 });
  const previous = page.getByRole("button", { name: "Previous version" });
  await expect(previous).toBeEnabled();
  await previous.click();
  await expect(page.getByText("0 versions", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Previous version" })).toBeDisabled();

  // Refresh restores the server-authored stage, pages, and selection defaults (FR-7.9).
  await page.reload();
  await expect(page).toHaveURL(/\/design$/);
  await expect(page.getByRole("heading", { name: "Design draft", exact: true })).toBeVisible();
  await expect(page.getByText(/All pages have a current design/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "Export deck" }).click();
  await expect(page.getByRole("dialog", { name: "Export deck" })).toBeVisible();
  await page.getByRole("button", { name: "Export PPTX" }).click();
  await expect(page.getByText("Export complete", { exact: true })).toBeVisible({ timeout: 180_000 });
  const download = page.getByRole("link", { name: /Download .*\.pptx/i });
  await expect(download).toBeVisible();
  const href = await download.getAttribute("href");
  expect(href).toContain("/api/exports/");
  await shot("07-export");

  const response = await page.request.get(href!);
  expect(response.status()).toBe(200);
  const body = await response.body();
  expect(body.length).toBeGreaterThan(1000);
  expect(body.subarray(0, 2).toString()).toBe("PK");
});
