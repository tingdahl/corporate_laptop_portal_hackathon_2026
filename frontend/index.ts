import type {
  PurchaseDetailsResponse,
  PurchaseSummary,
  ParsedTransaction,
  PurchaseEligibilityResponse,
} from "./contracts";
import { getCurrentUser, logout } from "./common";

const app = document.getElementById("app");

function render(message: string): void {
  if (!app) return;
  app.innerHTML = message;
}

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(decimals);
}

function anomalyBadge(key: string): string {
  const labels: Record<string, string> = {
    non_positive_net_amount: "Non-positive net — review required",
    potential_multi_item_bundle: "Potential multi-item bundle",
  };
  const label = labels[key] ?? key.replace(/_/g, " ");
  return `<span class="p-label--caution u-no-margin--left">${label}</span>`;
}

function renderTransactionsTable(transactions: ParsedTransaction[]): string {
  const rows = transactions
    .map(
      (t) =>
        `<tr>
          <td>${t.date}</td>
          <td>${t.currency}</td>
          <td class="u-align--right">${t.amount_signed >= 0 ? "+" : ""}${fmt(t.amount_signed)}</td>
        </tr>`,
    )
    .join("");
  return `
    <table class="p-table--mobile-card" style="width:100%;margin-top:0.5rem;">
      <thead>
        <tr>
          <th>Date</th>
          <th>Currency</th>
          <th class="u-align--right">Amount</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderPurchaseCard(purchase: PurchaseSummary, index: number): string {
  const badges = purchase.anomalies.map(anomalyBadge).join(" ");
  const depreciated =
    purchase.current_depreciated_value_usd !== null
      ? `$${fmt(purchase.current_depreciated_value_usd)} USD`
      : `${fmt(purchase.current_depreciated_value_local)} ${purchase.currency}`;

  const netLocal = `${fmt(purchase.net_amount_local)} ${purchase.currency}`;
  const netUsd = purchase.net_amount_usd !== null ? ` ($${fmt(purchase.net_amount_usd)} USD)` : "";
  const rate =
    purchase.exchange_rate_local_per_usd !== null
      ? `<span class="p-text--small u-text--muted"> · Rate: 1 USD = ${fmt(purchase.exchange_rate_local_per_usd, 4)} ${purchase.currency}</span>`
      : "";

  const refreshDate = `<span class="p-text--small ${new Date(purchase.next_refresh_date) <= new Date() ? "u-text--caution" : "u-text--muted"}">${purchase.next_refresh_date}${new Date(purchase.next_refresh_date) <= new Date() ? " — eligible now" : ""}</span>`;

  const txTable = renderTransactionsTable(purchase.transactions);

  return `
    <details class="p-accordion__group" ${index === 0 ? "open" : ""}>
      <summary class="p-accordion__tab" style="list-style:none;cursor:pointer;padding:0;">
        <div class="p-card" style="margin-bottom:0.5rem;">
          <div class="row">
            <div class="col-4">
              <p class="p-text--small u-text--muted" style="margin-bottom:0.25rem;">Purchase date</p>
              <p class="p-heading--5" style="margin-bottom:0;">${purchase.purchase_date}</p>
            </div>
            <div class="col-4">
              <p class="p-text--small u-text--muted" style="margin-bottom:0.25rem;">Net amount</p>
              <p class="p-heading--5" style="margin-bottom:0;">${netLocal}<span class="p-text--small">${netUsd}</span>${rate}</p>
            </div>
            <div class="col-4">
              <p class="p-text--small u-text--muted" style="margin-bottom:0.25rem;">Depreciated value</p>
              <p class="p-heading--5" style="margin-bottom:0;">${depreciated}</p>
            </div>
          </div>
          <div class="row" style="margin-top:0.5rem;">
            <div class="col-4">
              <p class="p-text--small u-text--muted" style="margin-bottom:0.25rem;">Next planned laptop refresh</p>
              <p class="p-text--default" style="margin-bottom:0;">${refreshDate}</p>
            </div>
          </div>
          ${badges ? `<div style="margin-top:0.5rem;">${badges}</div>` : ""}
          <p class="p-text--small u-text--muted" style="margin-bottom:0;margin-top:0.5rem;">
            ${purchase.transactions.length} transaction${purchase.transactions.length !== 1 ? "s" : ""}
            · window ends ${purchase.window_end_date}
            · click to ${index === 0 ? "collapse" : "expand"}
          </p>
        </div>
      </summary>
      <div class="p-card" style="margin-top:-0.5rem;border-top:none;padding-top:0.5rem;">
        <h4 class="p-heading--6">Underlying transactions</h4>
        ${txTable}
      </div>
    </details>`;
}

function renderPurchaseSection(data: PurchaseDetailsResponse): string {
  if (data.purchases.length === 0) {
    return `
      <section class="p-strip is-shallow">
        <div class="row">
          <div class="col-12">
            <h2 class="p-heading--4">Purchase History</h2>
            <p class="p-text--default">No laptop purchases found for your account.</p>
          </div>
        </div>
      </section>`;
  }

  const cards = data.purchases.map((p, i) => renderPurchaseCard(p, i)).join("");
  return `
    <section class="p-strip is-shallow">
      <div class="row">
        <div class="col-12">
          <h2 class="p-heading--4">Purchase History</h2>
          <p class="p-text--small u-text--muted">
            Interpreted laptop purchases for ${data.employee_email}.
            Purchases are preliminary interpretations — the actual purchase record is authoritative.
          </p>
        </div>
      </div>
      <div class="row">
        <div class="col-12">
          ${cards}
        </div>
      </div>
    </section>`;
}

function renderQuoteAction(eligibility: PurchaseEligibilityResponse): string {
  if (eligibility.eligible_for_new_laptop) {
    return `
      <section class="p-card">
        <h2 class="p-heading--5">New Laptop Quote</h2>
        <p class="p-text--default">Register and verify a laptop quote from a shopping cart screenshot.</p>
        <p class="p-text--default">Upload an image or PDF, review the extracted information, and submit for processing.</p>
        <a href="/new_quote.html" class="p-button--positive">Create New Quote</a>
      </section>
    `;
  }

  return `
    <section class="p-card">
      <h2 class="p-heading--5">New Laptop Quote</h2>
      <p class="p-text--default">You can create a new quote when the estimated refresh date is reached.</p>
      <p class="p-text--small u-text--muted">Writeoff period: ${eligibility.writeoff_months} months.</p>
      ${
        eligibility.next_planned_laptop_refresh
          ? `<p class="p-text--default"><strong>Estimated next eligibility:</strong> ${eligibility.next_planned_laptop_refresh}</p>`
          : ""
      }
    </section>
  `;
}

function buildDashboard(userEmail: string): void {
  if (!app) return;
  app.innerHTML = `
    <header class="p-strip is-shallow">
      <div class="row">
        <div class="col-9 col-medium-4">
          <h1 class="p-heading--2">Staff Portal</h1>
          <p class="p-text--default">Manage your laptop purchase and quote registration.</p>
        </div>
        <div class="col-3 col-medium-2 u-align--right">
          <div class="p-text--small" style="margin-bottom: 1rem;">Logged in as: <strong>${userEmail}</strong></div>
          <button class="p-button--base" id="logout-btn" type="button">Logout</button>
        </div>
      </div>
    </header>

    <div class="p-strip is-shallow" style="background-color: #f7f7f7; border: 2px solid #0e8420; padding: 1rem 0;">
      <div class="row">
        <div class="col-12">
          <div class="p-notification--information" style="margin-bottom: 0;">
            <div class="p-notification__content">
              <h3 class="p-notification__title">🚀 DEMO Navigation</h3>
              <p class="p-notification__message">Quick access to portal features:</p>
              <div style="margin-top: 0.5rem;">
                <a href="/new_quote.html" class="p-button--positive" style="margin-right: 0.5rem;">New Quote</a>
                <a href="/employees.html" class="p-button" style="margin-right: 0.5rem;">Employee Search</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <main>
      <div class="p-strip is-default">
        <div class="row">
          <div class="col-6 col-medium-4">
            <div id="quote-action">
              <section class="p-card">
                <h2 class="p-heading--5">New Laptop Quote</h2>
                <p class="p-text--default">
                  <i class="p-icon--spinner u-animation--spin" style="margin-right:0.5rem;"></i>
                  Checking eligibility…
                </p>
              </section>
            </div>
          </div>
        </div>
      </div>

      <div id="purchase-history">
        <div class="p-strip is-shallow">
          <div class="row">
            <div class="col-12">
              <h2 class="p-heading--4">Purchase History</h2>
              <p class="p-text--default">
                <i class="p-icon--spinner u-animation--spin" style="margin-right:0.5rem;"></i>
                Loading purchase history…
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  `;
}

async function loadQuoteEligibility(): Promise<void> {
  const section = document.getElementById("quote-action");
  if (!section) return;

  try {
    const resp = await fetch("/api/purchase_details/eligibility");
    if (!resp.ok) {
      section.innerHTML = `
        <section class="p-card">
          <h2 class="p-heading--5">New Laptop Quote</h2>
          <p class="p-text--default">Could not check eligibility right now.</p>
        </section>
      `;
      return;
    }
    const data = (await resp.json()) as PurchaseEligibilityResponse;
    section.innerHTML = renderQuoteAction(data);
  } catch {
    section.innerHTML = `
      <section class="p-card">
        <h2 class="p-heading--5">New Laptop Quote</h2>
        <p class="p-text--default">Could not check eligibility right now.</p>
      </section>
    `;
  }
}

async function loadPurchaseHistory(): Promise<void> {
  const section = document.getElementById("purchase-history");
  if (!section) return;

  try {
    const resp = await fetch("/api/purchase_details");
    if (!resp.ok) {
      section.innerHTML = `
        <div class="p-strip is-shallow">
          <div class="row"><div class="col-12">
            <div class="p-notification--caution">
              <div class="p-notification__content">
                <h5 class="p-notification__title">Could not load purchase history</h5>
                <p class="p-notification__message">Server returned ${resp.status}. Please try again later.</p>
              </div>
            </div>
          </div></div>
        </div>`;
      return;
    }
    const data = (await resp.json()) as PurchaseDetailsResponse;
    section.innerHTML = renderPurchaseSection(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unexpected error";
    section.innerHTML = `
      <div class="p-strip is-shallow">
        <div class="row"><div class="col-12">
          <div class="p-notification--negative">
            <div class="p-notification__content">
              <h5 class="p-notification__title">Failed to load purchase history</h5>
              <p class="p-notification__message">${msg}</p>
            </div>
          </div>
        </div></div>
      </div>`;
  }
}

async function main(): Promise<void> {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  buildDashboard(user.email);

  const logoutBtn = document.getElementById("logout-btn") as HTMLButtonElement | null;
  logoutBtn?.addEventListener("click", async () => {
    await logout();
  });

  void loadQuoteEligibility();
  void loadPurchaseHistory();
}

void main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : "Unexpected error";
  render(`Failed to start app: ${message}`);
});


