import { expect, type Page, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8100/api";

async function as(page: Page, user: string) {
  await page.addInitScript((u) => localStorage.setItem("lb.user", u), user);
}

test.describe("LedgerBot enterprise workflows", () => {
  test("dashboard loads and every module is reachable from the sidebar", async ({ page }) => {
    await as(page, "u-admin");
    await page.goto("/");
    await expect(page).toHaveURL(/\/overview$/);
    await expect(page.getByRole("heading", { name: "Operations Overview" })).toBeVisible();
    await expect(page.getByText("Pending match reviews")).toBeVisible();
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const [link, heading] of [["Inventory Catalog", "Inventory Catalog"], ["Match Review", "Match Review"], ["Suppliers", "Suppliers"],
      ["Data Ingestion", "Data Ingestion"], ["Offer Intelligence", "Offer Comparison"], ["Search Ranking", "Search Ranking · Preview"],
      ["Analytics", "Analytics"], ["Quality & Audit", "Quality & Audit"], ["Settings", "Settings"]]) {
      await nav.getByRole("link", { name: link, exact: true }).click();
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    }
  });

  test("search a hotel, open its canonical record and inspect supplier listings", async ({ page }) => {
    await as(page, "u-admin");
    await page.goto("/inventory/hotels");
    await page.getByLabel("Search inventory").fill("atlantis the palm");
    const row = page.getByRole("link", { name: /^Atlantis The Palm/ }).first();
    await expect(row).toBeVisible();
    await row.click();
    await expect(page.getByRole("heading", { level: 1, name: "Atlantis The Palm" })).toBeVisible();
    await page.getByRole("tab", { name: /Supplier records/ }).click();
    await expect(page.getByText("Learned source trust (truth discovery)")).toBeVisible();
    await expect(page.locator("tbody tr")).toHaveCount(5);
    await page.getByRole("tab", { name: "Matching evidence" }).click();
    await expect(page.getByText("Why nearby properties were kept separate")).toBeVisible();
    await expect(page.getByRole("link", { name: "Atlantis The Royal" })).toBeVisible();
  });

  test("a review decision changes the catalog, survives a reload and can be undone", async ({ page, request }) => {
    const cases = await (await request.get(`${API}/review/cases?status=open&page_size=200`)).json();
    const target = cases.items.find((c: any) => !c.mapping.same_property && !c.mapping.merge_conflict_suppliers.length);
    test.skip(!target, "no mergeable open case");
    await as(page, "u-admin");
    await page.goto(`/matching/review?case=${target.id}`);
    await page.getByRole("button", { name: "Confirm match" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("merges");
    await dialog.getByRole("button", { name: "Confirm match" }).click();
    await expect(page.getByText("Confirmed as the same property")).toBeVisible();
    await page.reload();
    await expect(page.getByText("Confirmed as the same property")).toBeVisible();
    const after = await (await request.get(`${API}/review/cases/${target.id}`)).json();
    expect(after.status).toBe("confirmed");
    expect(after.mapping.same_property).toBe(true);
    const hotel = await (await request.get(`${API}/inventory/hotel/${after.mapping.property_a}`)).json();
    expect(hotel.records.map((r: any) => r.record_id)).toEqual(expect.arrayContaining([target.record_a, target.record_b]));
    await page.getByRole("button", { name: "Reopen and undo" }).click();
    await page.getByLabel("Why is the decision being corrected?").fill("E2E test cleanup");
    await page.getByRole("dialog").getByRole("button", { name: "Reopen and undo" }).click();
    await expect(page.getByRole("button", { name: "Confirm match" })).toBeVisible();
    const reverted = await (await request.get(`${API}/review/cases/${target.id}`)).json();
    expect(reverted.status).toBe("open");
    expect(reverted.mapping.same_property).toBe(false);
    const audit = await (await request.get(`${API}/audit?entity_id=${target.id}`)).json();
    expect(audit.items.map((e: any) => e.action)).toEqual(expect.arrayContaining(["review.confirmed", "review.reopened"]));
  });

  test("roles without review permission cannot decide", async ({ page, request }) => {
    const cases = await (await request.get(`${API}/review/cases?status=open&page_size=1`)).json();
    await as(page, "u-sara");
    await page.goto(`/matching/review?case=${cases.items[0].id}`);
    await expect(page.getByRole("button", { name: "Confirm match" })).toBeDisabled();
    await expect(page.getByText(/can add notes but not decide/)).toBeVisible();
  });

  test("offer comparison recommends a coherent eligible offer", async ({ page, request }) => {
    const inv = await (await request.get(`${API}/inventory?q=atlantis%20the%20palm`)).json();
    const id = inv.items[0].id;
    const offers = await (await request.get(`${API}/offers/hotel/${id}?nights=3`)).json();
    const group = offers.rooms[0].groups[0];
    const rec = group.recommended;
    const row = group.offers.find((o: any) => o.offer_id === rec.offer_id);
    expect([rec.total, rec.cancel_hours, rec.payment, rec.supplier]).toEqual([row.total, row.cancel_hours, row.payment, row.supplier]);
    expect(rec.premium_pct).toBeLessThanOrEqual(offers.cap_pct);
    await as(page, "u-sara");
    await page.goto(`/offers/comparison?type=hotel&id=${id}`);
    await expect(page.getByText("Recommended").first()).toBeVisible();
    await expect(page.getByText(`₹${rec.total.toLocaleString("en-IN")}`).first()).toBeVisible();
  });

  test("sightseeing keeps access tiers and option inclusions apart", async ({ page }) => {
    await as(page, "u-admin");
    await page.goto("/inventory/sightseeing?q=burj");
    await expect(page.getByRole("link", { name: /Burj Khalifa: At the Top · Level 148/ }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Burj Khalifa: At the Top · Levels 124\/125/ }).first()).toBeVisible();
    await page.getByRole("link", { name: /Levels 124\/125/ }).first().click();
    await page.getByRole("tab", { name: "Matching evidence" }).click();
    await expect(page.getByText("Kept separate on purpose")).toBeVisible();
    await page.getByRole("tab", { name: /Options/ }).click();
    await expect(page.getByText(/Option · /).first()).toBeVisible();
  });
});
