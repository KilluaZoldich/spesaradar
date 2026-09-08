import { test, expect } from "../../apps/web/node_modules/@playwright/test";
async function select(page: any) {
  await page.goto("./");
  await page
    .getByRole("checkbox", { name: /Eurospin Catalogo nazionale/ })
    .check();
  await page.getByRole("checkbox", { name: /Lidl Catalogo nazionale/ }).check();
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Le tue offerte", exact: true }),
  ).toBeVisible();
}
test("Pages live: ricerca, categorie, dettaglio, aggiornamento e nessuna API", async ({
  page,
}) => {
  const errors: string[] = [],
    requests: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => requests.push(r.url()));
  await select(page);
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page.getByRole("button", { name: /Carne \d+/, exact: true }).click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  for (const label of await page
    .locator(".offer-card .category-label")
    .allTextContents())
    expect(label).toBe("Carne");
  await page.getByRole("button", { name: /Tutti \d+/, exact: true }).click();
  await page.getByRole("textbox", { name: "Cerca prodotti" }).fill("pollo");
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Cancella ricerca", exact: true })
    .click();
  await page.locator(".offer-card h3 button").first().click();
  await expect(page.getByRole("dialog")).toContainText("Ultima verifica");
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Controlla aggiornamenti", exact: true })
    .click();
  await expect(page.getByText(/Ultima pubblicazione caricata/)).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Le tue offerte", exact: true }),
  ).toBeVisible();
  expect(
    requests.filter(
      (url) =>
        url.includes("/api/") ||
        /^https:\/\/www\.(lidl|eurospin)\.it/.test(url),
    ),
  ).toEqual([]);
  expect(errors).toEqual([]);
});
test("Pages live: futuro, Eurospin, prezzo compatibile e mobile", async ({
  page,
}) => {
  await select(page);
  await page.getByRole("button", { name: "In arrivo", exact: true }).click();
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await page
    .getByLabel("Supermercato", { exact: true })
    .selectOption("eurospin");
  await expect(page.locator(".offer-card").first()).toBeVisible();
  for (const label of await page
    .locator(".offer-card .retailer")
    .allTextContents())
    expect(label).toBe("Eurospin");
  await page.getByLabel("Ordina offerte").selectOption("price-pack");
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await page
    .getByRole("button", { name: "Rimuovi filtro supermercato" })
    .click();
  await page.setViewportSize({ width: 360, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../../docs/pages-mobile.png" });
});
test("Pages live: accessibilità e snapshot senza capture private", async ({
  page,
  request,
  baseURL,
}) => {
  const { default: AxeBuilder } =
    await import("../../apps/web/node_modules/@axe-core/playwright/dist/index.mjs");
  await select(page);
  await expect(page.locator(".offer-card").first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const response = await request.get(new URL("catalog.json", baseURL).href);
  expect(response.ok()).toBe(true);
  const text = await response.text();
  expect(text).not.toContain("capture_id");
  expect(text).not.toContain(".private/");
  const snapshot = JSON.parse(text);
  expect(snapshot.records.length).toBeGreaterThan(0);
  expect(
    snapshot.records.every((r: any) => r.offer.data_origin === "official_live"),
  ).toBe(true);
  await page.screenshot({ path: "../../docs/pages-desktop.png" });
});
