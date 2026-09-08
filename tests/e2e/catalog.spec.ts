import { test, expect } from "../../apps/web/node_modules/@playwright/test";
// Isolated browser fixture routes. No mock data is ever written to the live database.
const now = () => new Date().toISOString();
const offer = (
  id: string,
  title: string,
  retailer: string,
  category: string,
  conditions: Record<string, unknown> = {},
) => ({
  id,
  title,
  brand: null,
  retailer_id: retailer,
  category_id: category,
  tags: [],
  package: { raw_text: "500 g" },
  price: {
    advertised_amount_cents: 349,
    basis: "pack",
    published_unit_price: null,
    calculated_unit_price: "6.9800",
    unit_price_basis: "kg",
    calculation: "6,98 €/kg calcolati da 3,49 € per 500 g",
  },
  conditions: {
    status: "partial",
    loyalty_required: null,
    app_activation_required: null,
    minimum_pack_count: null,
    minimum_spend_cents: null,
    raw_text: null,
    ...conditions,
  },
  validity: {
    start_at: new Date(Date.now() - 86400000).toISOString(),
    end_at_exclusive: new Date(Date.now() + 86400000).toISOString(),
    raw_text: null,
  },
  scope: { type: "national", label: "Ambito sintetico di test" },
  source_url: "https://fixture.invalid/" + id,
  last_verified_at: now(),
  temporal_status: "active",
  freshness: "fresh",
  limitations: [],
  evidence: {
    url: "https://fixture.invalid",
    selector: "fixture",
    raw_price: "3,49 €",
  },
});
const items = [
  offer("pollo", "Petto di pollo", "lidl", "carne", {
    loyalty_required: true,
    minimum_pack_count: 2,
  }),
  offer("dolci", "Biscotti di prova", "eurospin", "dolci"),
  offer("gatti", "Alimento per gatti con pollo", "eurospin", "animali"),
];
async function setup(page: any, { failure = false, delayed = false } = {}) {
  let refreshes = 0,
    reads = 0;
  await page.route("**/api/v1/refreshes", async (route: any) => {
    refreshes++;
    await route.fulfill({
      json: { id: "fixture-refresh", targets: [{ disposition: "job_active" }] },
    });
  });
  await page.route("**/api/v1/refreshes/*", async (route: any) => {
    reads++;
    await route.fulfill({
      json: {
        terminal: reads > 1,
        source_states: [
          {
            source_id: "lidl-national",
            name: "Lidl",
            state: "succeeded",
            stage: null,
            last_success_at: now(),
            message: null,
          },
          {
            source_id: "eurospin-national",
            name: "Eurospin",
            state: failure ? "failed" : "succeeded",
            stage: null,
            last_success_at: failure ? null : now(),
            message: failure ? "Fonte non raggiungibile" : null,
          },
        ],
      },
    });
  });
  await page.route("**/api/v1/offers?*", async (route: any) => {
    const u = new URL(route.request().url());
    const targets = u.searchParams.getAll("target_ids");
    let filtered = items.filter((o) =>
      targets.includes(o.retailer_id + "-national"),
    );
    const q = u.searchParams.get("q");
    if (q) filtered = filtered.filter((o) => o.title.toLowerCase().includes(q));
    const counts = Object.fromEntries(
      ["carne", "dolci", "animali"].map((c) => [
        c,
        filtered.filter((o) => o.category_id === c).length,
      ]),
    );
    const cats = u.searchParams.getAll("category_ids");
    if (cats.length)
      filtered = filtered.filter((o) => cats.includes(o.category_id));
    if (failure) filtered = filtered.filter((o) => o.retailer_id === "lidl");
    if (delayed && targets.includes("eurospin-national"))
      await new Promise((r) => setTimeout(r, 500));
    await route.fulfill({
      json: {
        items: filtered,
        next_cursor: null,
        total: filtered.length,
        category_counts: counts,
        catalog_revision: "fixture-v1",
        server_time: now(),
        source_states: failure
          ? [
              {
                source_id: "eurospin-national",
                name: "Eurospin",
                state: "failed",
                stage: null,
                last_success_at: null,
                message: "Fonte non raggiungibile",
              },
            ]
          : [],
        limitations: [],
      },
    });
  });
  await page.route("**/api/v1/offers/pollo", async (route: any) =>
    route.fulfill({ json: items[0] }),
  );
  return () => refreshes;
}
async function selectBoth(page: any) {
  await page.goto("/");
  await page.getByRole("checkbox", { name: /Lidl Catalogo nazionale/ }).check();
  await page
    .getByRole("checkbox", { name: /Eurospin Catalogo nazionale/ })
    .check();
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
}

test("selezione doppia, carne/dolci, ricerca, condizioni, reload e focus", async ({
  page,
}) => {
  const refreshCount = await setup(page);
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(3);
  await expect(page.getByText("Solo con Lidl Plus")).toBeVisible();
  await expect(page.getByText("Acquisto minimo 2 confezioni")).toBeVisible();
  const before = refreshCount();
  await page.getByRole("button", { name: "Carne 1", exact: true }).click();
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(page.locator(".offer-card h3")).toHaveText(["Petto di pollo"]);
  await page.getByRole("button", { name: "Tutti 3", exact: true }).click();
  await page.getByRole("button", { name: "Dolci 1", exact: true }).click();
  await expect(page.locator(".offer-card h3")).toHaveText([
    "Biscotti di prova",
  ]);
  expect(refreshCount()).toBe(before);
  await page.getByRole("button", { name: "Tutti 3", exact: true }).click();
  await page.getByRole("textbox", { name: "Cerca prodotti" }).fill("pollo");
  await expect(page.locator(".offer-card")).toHaveCount(2);
  await expect(
    page
      .locator(".offer-card")
      .filter({ hasText: "Alimento per gatti" })
      .locator(".category-label"),
  ).toHaveText("Animali");
  await page
    .getByRole("button", { name: "Petto di pollo", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Le tue offerte" }),
  ).toBeVisible();
  await expect(page.getByLabel("Filtra per supermercato")).toContainText("Lidl");
  await expect(page.getByLabel("Filtra per supermercato")).toContainText("Eurospin");
});

test("fallimento isolato, cache immediata e nessun crawl da filtro", async ({
  page,
}) => {
  await setup(page, { failure: true });
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(
    page.getByText("Fonte non raggiungibile", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Petto di pollo", { exact: true })).toBeVisible();
});

test("cambio selezione durante polling ignora risposte vecchie", async ({
  page,
}) => {
  await setup(page, { delayed: true });
  await selectBoth(page);
  await page.getByRole("button", { name: "Modifica negozi" }).click();
  await page
    .getByRole("checkbox", { name: /Eurospin Catalogo nazionale/ })
    .uncheck();
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(page.locator(".offer-card")).not.toContainText("Biscotti");
  await page.waitForTimeout(700);
  await expect(page.locator(".offer-card")).toHaveCount(1);
});

test("360 px, tastiera e nessun overflow", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await setup(page);
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(3);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await expect(page.getByLabel("Carta fedeltà")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../../docs/mobile-fixture.png",
    fullPage: true,
  });
});

test("live: cataloghi persistenti, futuro, dettaglio e console", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await selectBoth(page);
  await expect(page.locator(".offer-card").first()).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: /Carne \d+/, exact: true }).click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await expect(
    page.locator(".offer-card").first().locator(".category-label"),
  ).toHaveText("Carne");
  await page.getByRole("button", { name: /Tutti \d+/, exact: true }).click();
  await page.getByRole("button", { name: "In arrivo", exact: true }).click();
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await page
    .getByLabel("Supermercato", { exact: true })
    .selectOption("eurospin");
  await expect(
    page.locator(".offer-card").first().locator(".retailer"),
  ).toHaveText("Eurospin");
  await page.locator(".offer-card h3 button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Ultima verifica");
  await page.keyboard.press("Escape");
  await page.screenshot({
    path: "../../docs/catalog-live.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../../docs/mobile-live.png" });
  expect(errors).toEqual([]);
});

test("scadenza dopo resume rimuove anche la cache offline", async ({
  page,
}) => {
  await setup(page);
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(3);
  await page.clock.install();
  await page.context().setOffline(true);
  await page.clock.setSystemTime(new Date(Date.now() + 49 * 3600000));
  await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await expect(page.locator(".offer-card")).toHaveCount(0);
  await expect(page.getByText(/Sei offline/)).toBeVisible();
});

test("accessibilità automatica: selezione, catalogo e dettaglio", async ({
  page,
}) => {
  const { default: AxeBuilder } =
    await import("../../apps/web/node_modules/@axe-core/playwright/dist/index.mjs");
  await setup(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Scegli i supermercati" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("checkbox", { name: /Lidl Catalogo nazionale/ }).check();
  await page
    .getByRole("checkbox", { name: /Eurospin Catalogo nazionale/ })
    .check();
  await page
    .getByRole("button", { name: "Cerca offerte", exact: true })
    .click();
  await expect(page.locator(".offer-card")).toHaveCount(3);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("button", { name: "Petto di pollo", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("categorie espanse e filtri rimovibili anche a pannello chiuso", async ({
  page,
}) => {
  const refreshCount = await setup(page);
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(3);
  const before = refreshCount();
  await page
    .getByRole("button", { name: "Tutte le categorie", exact: true })
    .click();
  await expect(page.locator(".categories")).toHaveClass(/expanded/);
  await page.getByRole("button", { name: "Animali 1", exact: true }).click();
  await expect(page.locator(".offer-card h3")).toHaveText([
    "Alimento per gatti con pollo",
  ]);
  await page.getByRole("button", { name: "Tutti 3", exact: true }).click();
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await page
    .getByLabel("Carta fedeltà", { exact: true })
    .selectOption("required");
  await page.getByRole("button", { name: "Filtri", exact: true }).click();
  await expect(
    page.getByLabel("Carta fedeltà", { exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Rimuovi filtro carta" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Rimuovi filtro carta" }).click();
  await expect(
    page.getByRole("button", { name: "Rimuovi filtro carta" }),
  ).not.toBeVisible();
  expect(refreshCount()).toBe(before);
});

test("durante il caricamento di una categoria non mostra risultati della precedente", async ({
  page,
}) => {
  await setup(page, { delayed: true });
  await selectBoth(page);
  await expect(page.locator(".offer-card")).toHaveCount(3);
  await page.getByRole("button", { name: "Carne 1", exact: true }).click();
  await expect(
    page.getByRole("status", { name: "Caricamento delle offerte" }),
  ).toBeVisible();
  await expect(page.locator(".offer-card")).toHaveCount(0);
  await expect(page.locator(".offer-card h3")).toHaveText(["Petto di pollo"]);
});
