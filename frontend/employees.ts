import type {
  EmployeePurchaseRow,
  EmployeesPurchaseListResponse,
  PurchaseDetailsResponse,
  PurchaseSummary,
  ParsedTransaction,
} from "./contracts";
import { getCurrentUser, logout } from "./common";

const app = document.getElementById("app");

let employees: EmployeePurchaseRow[] = [];
let selectedEmployeeEmail = "";

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(decimals);
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

function renderShell(userEmail: string): void {
  if (!app) return;

  app.innerHTML = `
    <header class="p-strip is-shallow">
      <div class="row">
        <div class="col-8 col-medium-4">
          <h1 class="p-heading--2">Employees</h1>
          <p class="p-text--default">Employees with laptop purchases.</p>
        </div>
        <div class="col-4 col-medium-2 u-align--right">
          <div class="p-text--small" style="margin-bottom:1rem;">Logged in as: <strong>${userEmail}</strong></div>
          <button class="p-button--base" id="logout-btn" type="button">Logout</button>
        </div>
      </div>
    </header>

    <main class="p-strip is-default" style="position:relative; overflow:hidden;">
      <div class="row">
        <div class="col-12">
          <div class="p-card" style="margin-bottom:1rem;">
            <label class="p-form__label" for="employee-search">Search users</label>
            <input class="p-form-validation__input" id="employee-search" type="search" placeholder="Filter by e-mail" />
          </div>

          <div class="p-card">
            <table class="p-table--mobile-card" id="employees-table" style="width:100%;">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Latest purchase date</th>
                </tr>
              </thead>
              <tbody id="employees-table-body">
                <tr><td colspan="2">Loading…</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <aside id="employee-sidebar" style="position:absolute;top:0;right:-650px;width:650px;max-width:100%;height:100%;background:#fff;border-left:1px solid #d9d9d9;box-shadow:-8px 0 24px rgba(0,0,0,.08);transition:right .2s ease;overflow:auto;z-index:20;">
        <div style="padding:1rem 1.25rem;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:#fff;z-index:10;">
          <h2 class="p-heading--4" style="margin-bottom:0;">Employee details</h2>
          <button class="p-button--base" id="sidebar-close" type="button">Close</button>
        </div>
        <div id="employee-sidebar-content" style="padding:1rem 1.25rem;">
          <p class="p-text--muted">Select a user to see purchase details.</p>
        </div>
      </aside>
    </main>
  `;
}

function setSidebarOpen(open: boolean): void {
  const sidebar = document.getElementById("employee-sidebar");
  if (!sidebar) return;
  sidebar.setAttribute("style", sidebar.getAttribute("style")!.replace(/right:[^;]+;/, `right:${open ? "0" : "-650px"};`));
}

function renderTableRows(items: EmployeePurchaseRow[]): void {
  const body = document.getElementById("employees-table-body");
  if (!body) return;

  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="2">No matching users.</td></tr>`;
    return;
  }

  body.innerHTML = items
    .map(
      (row) => `
        <tr data-email="${row.employee_email}" style="cursor:pointer;">
          <td><a href="#" data-email="${row.employee_email}">${row.employee_email}</a></td>
          <td>${row.latest_purchase_date}</td>
        </tr>
      `,
    )
    .join("");

  body.querySelectorAll("tr[data-email]").forEach((tr) => {
    tr.addEventListener("click", (event) => {
      event.preventDefault();
      const email = (tr as HTMLElement).dataset.email;
      if (email) {
        void openEmployeeSidebar(email);
      }
    });
  });
}

function renderSidebarPurchases(data: PurchaseDetailsResponse): void {
  const container = document.getElementById("employee-sidebar-content");
  if (!container) return;

  if (data.purchases.length === 0) {
    container.innerHTML = `
      <p><strong>${data.employee_email}</strong></p>
      <p class="p-text--muted">No purchases found.</p>
    `;
    return;
  }

  const purchaseCards = data.purchases
    .map((purchase: PurchaseSummary, index: number) => {
      const netUsd = purchase.net_amount_usd !== null ? `$${fmt(purchase.net_amount_usd)} USD` : "—";
      const depUsd =
        purchase.current_depreciated_value_usd !== null
          ? `$${fmt(purchase.current_depreciated_value_usd)} USD`
          : `${fmt(purchase.current_depreciated_value_local)} ${purchase.currency}`;
      const refreshDate = `<span class="p-text--small ${new Date(purchase.next_refresh_date) <= new Date() ? "u-text--caution" : "u-text--muted"}">${purchase.next_refresh_date}${new Date(purchase.next_refresh_date) <= new Date() ? " — eligible now" : ""}</span>`;

      const txTable = renderTransactionsTable(purchase.transactions);

      return `
        <details class="p-accordion__group" ${index === 0 ? "open" : ""} style="margin-bottom:1rem;">
          <summary class="p-accordion__tab" style="list-style:none;cursor:pointer;padding:0;margin-bottom:0.5rem;">
            <div class="p-card" style="margin-bottom:0;">
              <h4 class="p-heading--5" style="margin-bottom:0.5rem;">Purchase ${purchase.purchase_date}</h4>
              <p style="margin-bottom:0.25rem;"><strong>Net amount:</strong> ${fmt(purchase.net_amount_local)} ${purchase.currency} (${netUsd})</p>
              <p style="margin-bottom:0.5rem;"><strong>Depreciated value:</strong> ${depUsd}</p>
              <p style="margin-bottom:0.25rem;"><strong>Next refresh:</strong> ${refreshDate}</p>
              <p class="p-text--small u-text--muted" style="margin-bottom:0;">
                ${purchase.transactions.length} transaction${purchase.transactions.length === 1 ? "" : "s"} · window ends ${purchase.window_end_date}
              </p>
            </div>
          </summary>
          <div style="padding-top:0.5rem;">
            <h5 class="p-heading--6">Transactions</h5>
            ${txTable}
          </div>
        </details>
      `;
    })
    .join("");

  container.innerHTML = `
    <p><strong>${data.employee_email}</strong></p>
    <hr />
    ${purchaseCards}
  `;
}

async function openEmployeeSidebar(email: string): Promise<void> {
  selectedEmployeeEmail = email;
  const container = document.getElementById("employee-sidebar-content");
  if (container) {
    container.innerHTML = `<p>Loading details for <strong>${email}</strong>…</p>`;
  }
  setSidebarOpen(true);

  try {
    const resp = await fetch(`/api/purchase_details/employee?email=${encodeURIComponent(email)}`);
    if (resp.status === 403) {
      if (container) {
        container.innerHTML = `<p class="p-text--negative">You do not have permission to view this user's details.</p>`;
      }
      return;
    }
    if (!resp.ok) {
      throw new Error(`Server returned ${resp.status}`);
    }
    const details = (await resp.json()) as PurchaseDetailsResponse;
    if (selectedEmployeeEmail !== email) {
      return;
    }
    renderSidebarPurchases(details);
  } catch (error) {
    if (container) {
      const message = error instanceof Error ? error.message : "Failed to load details";
      container.innerHTML = `<p class="p-text--negative">${message}</p>`;
    }
  }
}

async function loadEmployees(): Promise<void> {
  const response = await fetch("/api/purchase_details/employees");
  if (response.status === 403) {
    throw new Error("You do not have permission to view this page");
  }
  if (!response.ok) {
    throw new Error(`Failed to load employees (${response.status})`);
  }
  const data = (await response.json()) as EmployeesPurchaseListResponse;
  employees = data.employees;
  renderTableRows(employees);
}

function initializeSearch(): void {
  const input = document.getElementById("employee-search") as HTMLInputElement | null;
  if (!input) return;

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    const filtered = q ? employees.filter((e) => e.employee_email.toLowerCase().includes(q)) : employees;
    renderTableRows(filtered);
  });
}

async function main(): Promise<void> {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  renderShell(user.email);

  const logoutBtn = document.getElementById("logout-btn") as HTMLButtonElement | null;
  logoutBtn?.addEventListener("click", async () => {
    await logout();
  });

  const closeBtn = document.getElementById("sidebar-close") as HTMLButtonElement | null;
  closeBtn?.addEventListener("click", () => {
    setSidebarOpen(false);
  });

  initializeSearch();
  await loadEmployees();
}

void main().catch((error) => {
  if (!app) return;
  const message = error instanceof Error ? error.message : "Unexpected error";
  app.innerHTML = `<div class="p-strip"><div class="row"><div class="col-12"><div class="p-notification--negative"><div class="p-notification__content"><h5 class="p-notification__title">Failed to load employees page</h5><p class="p-notification__message">${message}</p></div></div></div></div></div>`;
});
