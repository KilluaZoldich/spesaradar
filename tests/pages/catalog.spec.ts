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
    .getByRole("navigation", { name: "Filtra per supermercato" })
    .getByRole("button", { name: "Tutti i supermercati", exact: true })
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
  await page.setViewportSize({ width: 1504, height: 1046 });
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
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../../docs/pages-desktop.png" });
});

test("Pages: nuova sede MD, carta e passaggio rapido alle offerte future", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("./");
  await page.getByLabel("Cerca supermercato o sede").fill("Rubens");
  await expect(page.getByRole("checkbox")).toHaveCount(1);
  await page.getByRole("checkbox", { name: /MD Punto vendita MILANO/ }).check();
  await page.getByRole("button", { name: "Cancella ricerca negozi" }).click();
  await page
    .getByRole("checkbox", { name: /Eurospin Catalogo nazionale/ })
    .check();
  await page.getByRole("checkbox", { name: /Lidl Catalogo nazionale/ }).check();
  await page.screenshot({ path: "../../docs/selection-expanded-mobile.png" });
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  const nav = page.getByRole("navigation", { name: "Filtra per supermercato" });
  await nav.getByRole("button", { name: "MD", exact: true }).click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  expect(await page.locator(".offer-card .retailer").allTextContents()).toEqual(
    expect.arrayContaining(["MD"]),
  );
  expect(
    (await page.locator(".offer-card .scope-caption").allTextContents()).every(
      (s) => s.includes("RUBENS"),
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await page
    .getByLabel("Carta fedeltà", { exact: true })
    .selectOption("required");
  await expect(page.locator(".offer-card").first()).toContainText(
    "Buona Spesa Card",
  );
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  const { default: AxeBuilder } =
    await import("../../apps/web/node_modules/@axe-core/playwright/dist/index.mjs");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "../../docs/md-mobile.png" });
  await page
    .locator(".offer-card")
    .first()
    .screenshot({ path: "../../docs/md-offer.png" });
  await page
    .getByRole("button", { name: "Rimuovi filtro carta", exact: true })
    .click();
  await nav.getByRole("button", { name: "Eurospin", exact: true }).click();
  const future = page.getByRole("button", {
    name: /Vedi \d+ offerte in arrivo/,
  });
  await expect(future).toBeVisible();
  await future.click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  expect(await page.locator(".offer-card .retailer").allTextContents()).toEqual(
    expect.arrayContaining(["Eurospin"]),
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.reload();
  await expect(
    page.getByRole("navigation", { name: "Filtra per supermercato" }),
  ).toContainText("MD");
});

test("Carpi 41012: una voce Conad, cambio sede e nuove insegne", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("./?cap=41012");
  await expect(page.getByLabel("Cerca supermercato o sede")).toHaveValue(
    "41012",
  );
  await expect(page.locator('[data-retailer="conad"]')).toHaveCount(1);
  await page.getByRole("button", { name: "Conad: scegli sede" }).click();
  await page.getByLabel("Punto vendita Conad").selectOption("conad-000350");
  await expect(page.locator('[data-retailer="famila"]')).toBeVisible();
  await expect(page.locator('[data-retailer="despar"]')).toBeVisible();
  await page.locator(".unsupported summary").click();
  await expect(page.locator(".unsupported")).toContainText("Coop Alleanza 3.0");
  await expect(page.locator(".unsupported")).toContainText("Sigma");
  await expect(page.locator(".unsupported")).toContainText("non acquisite");
  await page.screenshot({ path: "../../docs/carpi-selection-mobile.png" });
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page.getByRole("textbox", { name: "Cerca prodotti" }).fill("coca cola");
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(page.locator(".offer-card")).toContainText("1,89");
  await expect(page.locator(".offer-card")).toContainText("Solo con carta");
  await expect(page.locator(".offer-card")).toContainText("Carlo Marx");
  await page.locator(".offer-card h3 button").click();
  await expect(page.getByRole("dialog")).toContainText("PDF pagina 4");
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Cancella ricerca", exact: true })
    .click();
  await page.getByRole("button", { name: "In arrivo", exact: true }).click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page.screenshot({ path: "../../docs/conad-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const { default: AxeBuilder } =
    await import("../../apps/web/node_modules/@axe-core/playwright/dist/index.mjs");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(errors).toEqual([]);
});

test("Carpi: Famila e Interspar nel feed, cambio sede e preferenze senza duplicati", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("./?cap=41012");
  await page.getByRole("checkbox", { name: /Famila Punto vendita/ }).check();
  await page.getByRole("checkbox", { name: /Despar.*Punto vendita/ }).check();
  await page.getByRole("button", { name: "Conad: scegli sede" }).click();
  await page.getByLabel("Punto vendita Conad").selectOption("conad-000350");
  await page.getByRole("button", { name: "Conad: cambia sede" }).click();
  await page.getByLabel("Punto vendita Conad").selectOption("conad-010088");
  await page.screenshot({
    path: "../../docs/selection-one-brand-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Filtra per supermercato" });
  await nav.getByRole("button", { name: "Famila", exact: true }).click();
  await page.getByLabel("Cerca prodotti").fill("salmone norvegese");
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(page.locator(".offer-card")).toContainText("12,50");
  await page.locator(".offer-card h3 button").click();
  await expect(page.getByRole("dialog")).toContainText("PDF pagina 4");
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Cancella ricerca", exact: true })
    .click();
  await nav
    .getByRole("button", { name: "Despar / Interspar", exact: true })
    .click();
  await page.getByLabel("Cerca prodotti").fill("petto pollo");
  await expect(page.locator(".offer-card").first()).toContainText(
    "Interspar Carpi",
  );
  await page.screenshot({ path: "../../docs/despar-mobile.png" });
  const saved = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("spesaradar.preferences") || "{}"),
  );
  expect(
    saved.target_ids.filter((x: string) => x.startsWith("conad-")),
  ).toEqual(["conad-010088"]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Cancella ricerca", exact: true })
    .click();
  const { default: AxeBuilder } =
    await import("../../apps/web/node_modules/@axe-core/playwright/dist/index.mjs");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(errors).toEqual([]);
});
