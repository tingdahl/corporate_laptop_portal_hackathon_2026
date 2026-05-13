import type {
  InterpretQuoteResponse,
  AcceptQuoteRequest,
  AcceptQuoteResponse,
  QuoteOverrides,
} from "./contracts";
import { getCurrentUser, logout } from "./common";

let selectedFiles: File[] = [];
let latestInterpretationId = "";
let latestInterpretationData: InterpretQuoteResponse | null = null;

const MAX_PRICE_USD = 2900;

function updateSubmitButtonState(): void {
  const submitBtn = document.getElementById("submit-btn") as HTMLButtonElement | null;
  if (submitBtn) {
    submitBtn.disabled = selectedFiles.length === 0;
  }
}

function displaySelectedFiles(): void {
  const listContainer = document.getElementById("selected-files-list");
  const list = document.getElementById("selected-files");

  if (!list) {
    return;
  }

  if (selectedFiles.length === 0) {
    if (listContainer) {
      listContainer.style.display = "none";
    }
    list.innerHTML = "";
    return;
  }

  if (listContainer) {
    listContainer.style.display = "block";
  }

  list.innerHTML = selectedFiles
    .map((file, idx) => `<li key="${idx}">${file.name} (${(file.size / 1024).toFixed(1)} KB)</li>`)
    .join("");
}

function initClipboardPaste(): void {
  window.addEventListener("paste", (event: ClipboardEvent) => {
    const items = event.clipboardData?.items ?? [];
    for (const item of items) {
      if (item.type === "image/png" || item.type === "image/jpeg") {
        const file = item.getAsFile();
        if (!file) {
          continue;
        }
        if (!selectedFiles.find((existing) => existing.name === file.name && existing.size === file.size)) {
          selectedFiles.push(file);
        }
      }
    }

    if (selectedFiles.length > 0) {
      const status = document.getElementById("status");
      if (status) {
        status.textContent = `Selected ${selectedFiles.length} file(s)`;
      }
      displaySelectedFiles();
      updateSubmitButtonState();
    }
  });
}

function formatCurrency(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toFixed(decimals);
}

function getComplianceSymbol(passes: boolean | null | undefined): { color: string; text: string } {
  if (passes === true) {
    return { color: "#0f7b3a", text: "✓" };
  }
  if (passes === false) {
    return { color: "#c7162b", text: "✗" };
  }
  return { color: "#666", text: "?" };
}

function calculateCompliancePrice(): number | null {
  if (!latestInterpretationData) {
    return null;
  }

  const fields = latestInterpretationData.fields;
  const rate = latestInterpretationData.exchange_rate.rate_local_per_usd;

  // Get current override values
  const priceOverride = (document.getElementById("override-price") as HTMLInputElement)?.value?.trim();
  const shippingOverride = (document.getElementById("override-includes-shipping") as HTMLSelectElement)?.value;
  const warrantyOverride = (document.getElementById("override-includes-warranty") as HTMLSelectElement)?.value;

  // Determine effective values (override takes precedence)
  let quotedPrice = fields.quoted_price;
  if (priceOverride) {
    const parsed = parseFloat(priceOverride);
    if (!isNaN(parsed)) {
      quotedPrice = parsed;
    }
  }

  if (quotedPrice === null || !rate) {
    return null;
  }

  // Determine inclusion flags (override or detected)
  const warrantyIncluded = warrantyOverride ? warrantyOverride === "true" : fields.includes_warranty;
  const shippingIncluded = shippingOverride ? shippingOverride === "true" : fields.includes_shipping;

  // If we don't know, can't calculate
  if (warrantyIncluded === null || shippingIncluded === null) {
    return null;
  }

  let targetPrice = quotedPrice;

  // Remove shipping if included
  if (shippingIncluded) {
    if (fields.shipping_cost === null) {
      return null;
    }
    targetPrice -= fields.shipping_cost;
  }

  // Add warranty if not included
  if (!warrantyIncluded) {
    if (fields.warranty_cost === null) {
      return null;
    }
    targetPrice += fields.warranty_cost;
  }

  // Convert to USD
  return targetPrice / rate;
}

function updateCompliancePriceDisplay(): void {
  const compliancePrice = calculateCompliancePrice();
  const pricePass = compliancePrice !== null ? compliancePrice <= MAX_PRICE_USD : null;
  
  // Update the compliance price value
  const priceValueEl = document.getElementById("compliance-price-usd");
  if (priceValueEl) {
    priceValueEl.textContent = compliancePrice !== null
      ? `$${formatCurrency(compliancePrice)} USD`
      : "-";
  }
  
  // Update the compliance symbol
  const priceSymbol = getComplianceSymbol(pricePass);
  const priceEl = document.getElementById("status-price");
  if (priceEl) {
    priceEl.textContent = priceSymbol.text;
    priceEl.style.color = priceSymbol.color;
  }
}

function setupOverrideListeners(): void {
  // All overrides require backend re-interpretation for full pricing calculator
  const overrideIds = [
    "override-includes-tax",
    "override-includes-shipping",
    "override-includes-warranty"
  ];

  overrideIds.forEach(id => {
    const element = document.getElementById(id);
    if (element && !(element as any)._hasReinterpretListener) {
      element.addEventListener("change", async () => {
        if (selectedFiles.length > 0) {
          await uploadAndInterpret();
        }
      });
      (element as any)._hasReinterpretListener = true;
    }
  });

  // For currency and price overrides, trigger re-interpretation on blur
  const reinterpretIds = ["override-currency", "override-price"];
  reinterpretIds.forEach(id => {
    const element = document.getElementById(id);
    if (element && !(element as any)._hasReinterpretListener) {
      element.addEventListener("blur", async () => {
        const input = element as HTMLInputElement;
        if (input.value.trim() && selectedFiles.length > 0) {
          await uploadAndInterpret();
        }
      });
      (element as any)._hasReinterpretListener = true;
    }
  });
}

function buildFinanceOverrides(): QuoteOverrides {
  const overrides: QuoteOverrides = {};

  const currencyOverride = (document.getElementById("override-currency") as HTMLInputElement | null)?.value
    ?.trim()
    .toUpperCase()
    .replace(/[^A-Z]/g, "")
    .slice(0, 4);
  if (currencyOverride) {
    overrides.currency_override = currencyOverride;
  }

  const priceOverride = (document.getElementById("override-price") as HTMLInputElement | null)?.value
    ?.trim()
    .replace(/[^0-9.]/g, "");
  if (priceOverride) {
    overrides.price_override_local = priceOverride;
  }

  const includesTax = (document.getElementById("override-includes-tax") as HTMLSelectElement | null)?.value;
  if (includesTax === "true") {
    overrides.includes_tax = true;
  } else if (includesTax === "false") {
    overrides.includes_tax = false;
  }

  const includesShipping = (document.getElementById("override-includes-shipping") as HTMLSelectElement | null)?.value;
  if (includesShipping === "true") {
    overrides.includes_shipping = true;
  } else if (includesShipping === "false") {
    overrides.includes_shipping = false;
  }

  const includesWarranty = (document.getElementById("override-includes-warranty") as HTMLSelectElement | null)?.value;
  if (includesWarranty === "true") {
    overrides.includes_warranty = true;
  } else if (includesWarranty === "false") {
    overrides.includes_warranty = false;
  }

  return overrides;
}

function initializeCollapsibles(): void {
  const toggleButtons = [
    { id: "toggle-preview", contentId: "preview-content" },
    { id: "toggle-analysis", contentId: "analysis-content" },
    { id: "toggle-finance", contentId: "finance-content" },
  ];

  toggleButtons.forEach(({ id, contentId }) => {
    const btn = document.getElementById(id) as HTMLButtonElement | null;
    const content = document.getElementById(contentId) as HTMLDivElement | null;
    if (btn && content) {
      btn.addEventListener("click", () => {
        const isHidden = content.style.display === "none";
        content.style.display = isHidden ? "block" : "none";
        btn.textContent = isHidden ? "↓" : "→";
      });
    }
  });
}

async function uploadAndInterpret(): Promise<void> {
  const status = document.getElementById("status");
  if (selectedFiles.length === 0) {
    if (status) {
      status.textContent = "Please select or paste files first.";
    }
    return;
  }

  const fd = new FormData();
  selectedFiles.forEach((file) => {
    fd.append("files", file);
  });
  const overrides = buildFinanceOverrides();
  if (overrides.currency_override) {
    fd.append("currency_override", overrides.currency_override);
  }
  if (overrides.price_override_local) {
    fd.append("price_override_local", overrides.price_override_local);
  }
  if (overrides.includes_tax !== undefined) {
    fd.append("includes_tax", String(overrides.includes_tax));
  }
  if (overrides.includes_shipping !== undefined) {
    fd.append("includes_shipping", String(overrides.includes_shipping));
  }
  if (overrides.includes_warranty !== undefined) {
    fd.append("includes_warranty", String(overrides.includes_warranty));
  }

  if (status) {
    status.textContent = "Interpreting quote...";
  }

  try {
    const resp = await fetch("/api/new_laptop", { method: "POST", body: fd });
    if (!resp.ok) {
      const txt = await resp.text();
      if (status) {
        status.textContent = `Upload failed: ${txt}`;
      }
      return;
    }

    const data = (await resp.json()) as InterpretQuoteResponse;
    latestInterpretationId = data.interpretation_id;
    latestInterpretationData = data;

    if (status) {
      status.textContent = "Quote interpreted. Review the details below.";
    }

    // Display preview if available
    const resultsSection = document.getElementById("results-section");
    const previewContent = document.getElementById("preview-content");
    if (resultsSection) {
      resultsSection.classList.remove("u-hide");
    }
    
    // Display all processed images
    if (previewContent && data.processed_image_urls && data.processed_image_urls.length > 0) {
      previewContent.innerHTML = data.processed_image_urls
        .map((url, idx) => 
          `<div>
            <p class="p-text--small u-text--muted" style="margin-bottom: 0.5rem;">Upload ${idx + 1} of ${data.processed_image_urls.length}</p>
            <img src="${url}" alt="Processed image ${idx + 1}" style="max-width: 100%; border: 1px solid #d9d9d9;" />
          </div>`
        )
        .join("");
    } else if (previewContent && data.processed_image_url) {
      // Fallback for backwards compatibility
      previewContent.innerHTML = `<img src="${data.processed_image_url}" alt="Processed image preview" style="max-width: 100%; border: 1px solid #d9d9d9;" />`;
    }

    // Display extracted fields
    const analysisSection = document.getElementById("analysis-section");
    if (analysisSection) {
      analysisSection.classList.remove("u-hide");
    }
    const fields = data.fields;
    document.getElementById("cpu-model")!.textContent = fields.cpu_model ?? "-";
    document.getElementById("cpu-cores")!.textContent = fields.cpu_cores ? `${fields.cpu_cores}` : "-";
    document.getElementById("ram-gb")!.textContent = fields.ram_gb ? `${fields.ram_gb} GB` : "-";
    document.getElementById("disk-gb")!.textContent = fields.disk_gb ? `${fields.disk_gb} GB` : "-";
    
    // Build label for quoted price showing what's included
    let priceLabel = "Quoted Price";
    if (fields.includes_warranty !== null || fields.includes_tax !== null || fields.includes_shipping !== null) {
      const included: string[] = [];
      if (fields.includes_warranty) included.push("warranty");
      if (fields.includes_tax) included.push("tax");
      if (fields.includes_shipping) included.push("shipping");
      if (included.length > 0) {
        priceLabel += ` (incl. ${included.join(", ")})`;
      }
    }

    // Display pricing and calculator info in Finance section
    const financeSection = document.getElementById("finance-section");
    if (financeSection) {
      financeSection.classList.remove("u-hide");
    }
    const financeContent = document.getElementById("finance-content");
    if (financeContent && financeContent.style.display === "none") {
      financeContent.style.display = "block";
    }
    
    // Helper to format boolean as Yes/No/Don't Know
    const formatBool = (val: boolean | null): string => {
      if (val === null) return "Don't Know";
      return val ? "Yes" : "No";
    };
    
    document.getElementById("detected-currency")!.textContent = fields.currency || "-";
    document.getElementById("quoted-price")!.textContent = fields.quoted_price
      ? `${formatCurrency(fields.quoted_price)} ${fields.currency}`
      : "-";
    
    // Display detected inclusion flags
    document.getElementById("detected-includes-tax")!.textContent = formatBool(fields.includes_tax);
    document.getElementById("detected-includes-shipping")!.textContent = formatBool(fields.includes_shipping);
    
    // "Includes Minimum 3 Years Warranty" checks both warranty presence and duration
    const hasMinWarranty = (fields.includes_warranty === true && fields.warranty_years !== null && fields.warranty_years >= 3.0);
    document.getElementById("detected-includes-warranty")!.textContent = formatBool(hasMinWarranty ? true : (fields.warranty_years === null || fields.includes_warranty === null) ? null : false);
    
    const exchangeRate = data.exchange_rate;
    document.getElementById("exchange-rate")!.textContent = exchangeRate
      ? `1 USD = ${formatCurrency(exchangeRate.rate_local_per_usd)} ${exchangeRate.currency}`
      : "-";
    document.getElementById("price-usd")!.textContent = fields.quoted_price && exchangeRate
      ? `${formatCurrency(fields.quoted_price / exchangeRate.rate_local_per_usd)} USD`
      : "-";
    
    // Calculate and display compliance price
    try {
      updateCompliancePriceDisplay();
    } catch (e) {
      console.error("Error updating compliance price:", e);
      // Set default values if calculation fails
      const priceValueEl = document.getElementById("compliance-price-usd");
      if (priceValueEl) priceValueEl.textContent = "-";
    }

    // Display calculator results
    const pricing = data.pricing;
    document.getElementById("calc-laptop-price")!.textContent = formatCurrency(
      pricing.laptop_price_incl_warranty_usd
    );
    document.getElementById("calc-taxes")!.textContent = formatCurrency(pricing.taxes_usd);
    document.getElementById("calc-shipping")!.textContent = formatCurrency(pricing.shipping_usd);
    document.getElementById("calc-total")!.textContent = formatCurrency(pricing.total_purchase_usd);
    document.getElementById("calc-canonical")!.textContent = formatCurrency(pricing.canonical_reimbursed_usd);
    document.getElementById("calc-employee")!.textContent = formatCurrency(pricing.employee_own_expense_usd);

    // Display compliance symbols next to extracted values
    const compliance = data.compliance;
    const cpuModelSymbol = getComplianceSymbol(compliance.cpu_pass);
    const cpuCoresSymbol = getComplianceSymbol(compliance.cpu_pass);
    const ramSymbol = getComplianceSymbol(compliance.ram_pass);
    const diskSymbol = getComplianceSymbol(compliance.disk_pass);

    const cpuModelEl = document.getElementById("status-cpu-model")!;
    cpuModelEl.textContent = cpuModelSymbol.text;
    cpuModelEl.style.color = cpuModelSymbol.color;

    const cpuCoresEl = document.getElementById("status-cpu-cores")!;
    cpuCoresEl.textContent = cpuCoresSymbol.text;
    cpuCoresEl.style.color = cpuCoresSymbol.color;

    const ramEl = document.getElementById("status-ram")!;
    ramEl.textContent = ramSymbol.text;
    ramEl.style.color = ramSymbol.color;

    const diskEl = document.getElementById("status-disk")!;
    diskEl.textContent = diskSymbol.text;
    diskEl.style.color = diskSymbol.color;

    const priceEl = document.getElementById("status-price")!;
    priceEl.textContent = getComplianceSymbol(compliance.price_pass).text;
    priceEl.style.color = getComplianceSymbol(compliance.price_pass).color;

    // Setup event listeners for override inputs to recalculate price compliance
    setupOverrideListeners();

    // Show action section
    const actionSection = document.getElementById("action-section");
    if (actionSection) {
      actionSection.classList.remove("u-hide");
    }
  } catch (error) {
    if (status) {
      status.textContent = `Error: ${error instanceof Error ? error.message : "Unknown error"}`;
    }
  }
}

async function acceptAndUpload(): Promise<void> {
  const actionStatus = document.getElementById("action-status");
  if (!latestInterpretationId) {
    if (actionStatus) {
      actionStatus.textContent = "No interpreted quote to accept.";
    }
    return;
  }

  if (actionStatus) {
    actionStatus.textContent = "Generating evidence PDF...";
  }

  try {
    const overrides = buildFinanceOverrides();
    const body: AcceptQuoteRequest = {};
    if (Object.keys(overrides).length > 0) {
      body.overrides = overrides;
    }

    const resp = await fetch(`/api/new_laptop/${latestInterpretationId}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const txt = await resp.text();
      if (actionStatus) {
        actionStatus.textContent = `Failed: ${txt}`;
      }
      return;
    }

    // Parse JSON response with download URL
    const data = (await resp.json()) as AcceptQuoteResponse;

    // Download the PDF
    if (actionStatus) {
      actionStatus.textContent = "Downloading PDF...";
    }

    const downloadResp = await fetch(data.download_url);
    if (!downloadResp.ok) {
      if (actionStatus) {
        actionStatus.textContent = "Failed to download PDF.";
        actionStatus.style.color = "red";
      }
      return;
    }

    const blob = await downloadResp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.evidence_filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    // Show success message
    if (actionStatus) {
      actionStatus.textContent = `✓ Evidence PDF downloaded: ${data.evidence_filename}`;
      actionStatus.style.color = "green";
    }

    // Hide action section after successful download
    const actionSection = document.getElementById("action-section");
    if (actionSection) {
      setTimeout(() => {
        actionSection.classList.add("u-hide");
      }, 5000);
    }
  } catch (error) {
    if (actionStatus) {
      actionStatus.textContent = `Error: ${error instanceof Error ? error.message : "Unknown error"}`;
      actionStatus.style.color = "red";
    }
  }
}

async function main(): Promise<void> {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  initializeCollapsibles();
  initClipboardPaste();

  const fileInput = document.getElementById("file-input") as HTMLInputElement | null;
  const dropZone = document.getElementById("drop-zone") as HTMLDivElement | null;
  const submitBtn = document.getElementById("submit-btn") as HTMLButtonElement | null;
  const acceptBtn = document.getElementById("accept-btn") as HTMLButtonElement | null;
  const logoutBtn = document.getElementById("logout-btn") as HTMLButtonElement | null;

  function handleMultipleFileSelection(files: FileList | null): void {
    if (!files) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file && (file.type === "image/png" || file.type === "image/jpeg" || file.type === "application/pdf")) {
        // Avoid duplicates
        if (!selectedFiles.find((f) => f.name === file.name && f.size === file.size)) {
          selectedFiles.push(file);
        }
      }
    }
    const status = document.getElementById("status");
    if (status) {
      status.textContent = `Selected ${selectedFiles.length} file(s)`;
    }
    displaySelectedFiles();
    updateSubmitButtonState();
  }

  // File input change handler
  fileInput?.addEventListener("change", () => {
    handleMultipleFileSelection(fileInput.files);
  });

  // Drag and drop handlers
  if (dropZone) {
    dropZone.addEventListener("click", () => {
      fileInput?.click();
    });

    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.style.backgroundColor = "#e5e5e5";
      dropZone.style.borderColor = "#0f7b3a";
    });

    dropZone.addEventListener("dragleave", () => {
      dropZone.style.backgroundColor = "#f8f8f8";
      dropZone.style.borderColor = "#d9d9d9";
    });

    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.backgroundColor = "#f8f8f8";
      dropZone.style.borderColor = "#d9d9d9";
      handleMultipleFileSelection(e.dataTransfer?.files ?? null);
    });
  }

  // Initial button state
  updateSubmitButtonState();

  submitBtn?.addEventListener("click", () => {
    void uploadAndInterpret();
  });

  acceptBtn?.addEventListener("click", () => {
    void acceptAndUpload();
  });

  logoutBtn?.addEventListener("click", () => {
    void logout();
  });
}

void main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : "Unexpected error";
  console.error(message);
});
