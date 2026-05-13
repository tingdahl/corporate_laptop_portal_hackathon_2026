import { logout, requireAuthenticatedUser } from "./common";

type CsvLifecycleStatus = "Generated" | "Submitted" | "Processed";

type EligibleEmployee = {
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  first_day_of_employment_utc?: string | null;
  eligibility_date_utc?: string | null;
  waiting_since_utc?: string | null;
  waiting_list?: boolean;
};

type OnboardingEligibleResponse = {
  counts?: {
    eligible_total?: number;
    waiting_list_total?: number;
  };
  eligible_employees?: EligibleEmployee[];
  waiting_list_employees?: EligibleEmployee[];
};

type CsvFileSummary = {
  id: string;
  filename: string;
  status: CsvLifecycleStatus;
  row_count?: number;
  created_at_utc?: string;
};

type CsvListResponse = {
  csv_files?: CsvFileSummary[];
};

type GenerateCsvResponse = {
  csv?: CsvFileSummary;
};

const ALL_CSV_STATUSES: CsvLifecycleStatus[] = ["Generated", "Submitted", "Processed"];

function setStatus(message: string): void {
  const status = document.getElementById("status");
  if (status) {
    status.textContent = message;
  }
}

function formatUtc(value?: string): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toISOString();
}

async function parseResponseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

function renderError(message: string): void {
  setStatus(message);
}

function setUserEmail(email: string): void {
  const userEmail = document.getElementById("user-email");
  if (userEmail) {
    userEmail.textContent = email;
  }
}

function renderCounts(response: OnboardingEligibleResponse): void {
  const eligibleTotal = response.counts?.eligible_total ?? response.eligible_employees?.length ?? 0;
  const waitingListTotal = response.counts?.waiting_list_total ?? response.waiting_list_employees?.length ?? 0;

  const eligibleCount = document.getElementById("eligible-count");
  const waitingListCount = document.getElementById("waiting-list-count");
  if (eligibleCount) {
    eligibleCount.textContent = String(eligibleTotal);
  }
  if (waitingListCount) {
    waitingListCount.textContent = String(waitingListTotal);
  }
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const normalized = value.trim();
  if (!normalized) {
    return "-";
  }
  if (normalized.length >= 10) {
    return normalized.slice(0, 10);
  }
  return normalized;
}

function buildEmailCell(employee: EligibleEmployee): HTMLTableCellElement {
  const cell = document.createElement("td");
  cell.textContent = employee.email;
  return cell;
}

function renderEligibleTable(elementId: string, employees: EligibleEmployee[] = []): void {
  const root = document.getElementById(elementId);
  if (!root) {
    return;
  }

  root.textContent = "";

  if (employees.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    cell.textContent = "No employees found.";
    row.appendChild(cell);
    root.appendChild(row);
    return;
  }

  for (const employee of employees) {
    const row = document.createElement("tr");
    row.appendChild(buildEmailCell(employee));

    const referenceDateCell = document.createElement("td");
    referenceDateCell.textContent = formatDate(employee.first_day_of_employment_utc);
    row.appendChild(referenceDateCell);

    root.appendChild(row);
  }
}

function renderWaitingTable(elementId: string, employees: EligibleEmployee[] = []): void {
  const root = document.getElementById(elementId);
  if (!root) {
    return;
  }

  root.textContent = "";

  if (employees.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    cell.textContent = "No employees found.";
    row.appendChild(cell);
    root.appendChild(row);
    return;
  }

  for (const employee of employees) {
    const row = document.createElement("tr");
    row.appendChild(buildEmailCell(employee));

    const waitingSinceCell = document.createElement("td");
    waitingSinceCell.textContent = formatDate(employee.waiting_since_utc);
    row.appendChild(waitingSinceCell);

    root.appendChild(row);
  }
}

function buildStatusSelect(currentStatus: CsvLifecycleStatus, fileId: string): HTMLSelectElement {
  const select = document.createElement("select");
  select.id = `status-${fileId}`;
  select.className = "u-no-margin--bottom";

  for (const status of ALL_CSV_STATUSES) {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status;
    option.selected = status === currentStatus;
    select.appendChild(option);
  }

  return select;
}

async function changeCsvStatus(file: CsvFileSummary): Promise<void> {
  const select = document.getElementById(`status-${file.id}`) as HTMLSelectElement | null;
  const targetStatus = (select?.value ?? file.status) as CsvLifecycleStatus;

  if (targetStatus === file.status) {
    setStatus("No status change requested.");
    return;
  }

  const confirmed = window.confirm(
    `Change status for ${file.filename} from ${file.status} to ${targetStatus}?`
  );
  if (!confirmed) {
    setStatus("Status change cancelled.");
    return;
  }

  const sendInstructionEmailsOnProcessed = targetStatus === "Processed";

  setStatus(`Updating status for ${file.filename}...`);
  const response = await fetch(`/api/onboarding/csvs/${encodeURIComponent(file.id)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_status: targetStatus,
      confirm: true,
      send_instruction_emails_on_processed: sendInstructionEmailsOnProcessed,
    }),
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || "Failed to update CSV status.");
  }

  setStatus(`Status updated to ${targetStatus}.`);
  await loadCsvFiles();
}

function renderCsvFiles(files: CsvFileSummary[]): void {
  const tbody = document.getElementById("csv-files-body");
  if (!tbody) {
    return;
  }

  tbody.textContent = "";

  if (files.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No CSV files found.";
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  for (const file of files) {
    const row = document.createElement("tr");

    const filenameCell = document.createElement("td");
    filenameCell.textContent = file.filename;
    row.appendChild(filenameCell);

    const statusCell = document.createElement("td");
    statusCell.textContent = file.status;
    row.appendChild(statusCell);

    const rowsCell = document.createElement("td");
    rowsCell.textContent = String(file.row_count ?? 0);
    row.appendChild(rowsCell);

    const createdCell = document.createElement("td");
    createdCell.textContent = formatUtc(file.created_at_utc);
    row.appendChild(createdCell);

    const actionsCell = document.createElement("td");
    const select = buildStatusSelect(file.status, file.id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "p-button";
    button.textContent = "Update status";
    button.addEventListener("click", () => {
      void changeCsvStatus(file).catch((error: unknown) => {
        renderError(error instanceof Error ? error.message : "Failed to update CSV status.");
      });
    });

    actionsCell.appendChild(select);
    actionsCell.appendChild(button);
    row.appendChild(actionsCell);

    tbody.appendChild(row);
  }
}

async function loadCsvFiles(): Promise<void> {
  const response = await fetch("/api/onboarding/csvs");
  if (!response.ok) {
    const tbody = document.getElementById("csv-files-body");
    if (tbody) {
      tbody.innerHTML = "<tr><td colspan=\"5\">CSV lifecycle API is not available yet.</td></tr>";
    }
    return;
  }

  const data = await parseResponseOrThrow<CsvListResponse>(response);
  renderCsvFiles(data.csv_files ?? []);
}

async function generateCsv(): Promise<void> {
  setStatus("Generating onboarding CSV...");
  const response = await fetch("/api/onboarding/csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dry_run: false,
      include_recovered_waiting_list_employees: true,
    }),
  });

  const data = await parseResponseOrThrow<GenerateCsvResponse>(response);
  const filename = data.csv?.filename;
  setStatus(filename ? `Generated ${filename}.` : "CSV generated successfully.");
  await Promise.all([loadOnboardingData(), loadCsvFiles()]);
}

async function loadOnboardingData(): Promise<void> {
  setStatus("Loading onboarding data...");

  const response = await fetch("/api/onboarding/eligible");
  if (!response.ok) {
    renderError("Onboarding API is not available yet. Frontend scaffold is ready.");
    return;
  }

  const data = (await response.json()) as OnboardingEligibleResponse;
  renderCounts(data);
  renderEligibleTable("eligible-list", data.eligible_employees);
  renderWaitingTable("waiting-list", data.waiting_list_employees);
  setStatus("Onboarding data loaded.");
}

async function bootstrap(): Promise<void> {
  const user = await requireAuthenticatedUser();
  setUserEmail(user.email);

  const logoutButton = document.getElementById("logout-btn");
  logoutButton?.addEventListener("click", () => {
    void logout();
  });

  const refreshButton = document.getElementById("refresh-btn");
  refreshButton?.addEventListener("click", () => {
    void Promise.all([loadOnboardingData(), loadCsvFiles()]).catch((error: unknown) => {
      renderError(error instanceof Error ? error.message : "Failed to refresh onboarding data.");
    });
  });

  const generateCsvButton = document.getElementById("generate-csv-btn");
  generateCsvButton?.addEventListener("click", () => {
    void generateCsv().catch((error: unknown) => {
      renderError(error instanceof Error ? error.message : "Failed to generate CSV.");
    });
  });

  await Promise.all([loadOnboardingData(), loadCsvFiles()]);
}

void bootstrap().catch((error: unknown) => {
  renderError(error instanceof Error ? error.message : "Failed to initialize onboarding page.");
});
