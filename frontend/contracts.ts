// TypeScript definitions for API contracts
// These mirror the backend Pydantic models in backend/contracts/quotes.py

export interface ExtractedLaptopFields {
  cpu_model: string | null;
  cpu_cores: number | null;
  ram_gb: number | null;
  disk_gb: number | null;
  quoted_price: number | null;
  includes_warranty: boolean | null;
  includes_tax: boolean | null;
  includes_shipping: boolean | null;
  warranty_cost: number | null;
  tax_amount: number | null;
  shipping_cost: number | null;
  warranty_years: number | null;
  currency: string;
}

export interface ExchangeRateInfo {
  currency: string;
  rate_local_per_usd: number;
  captured_at_utc: string;
}

export interface PricingCalculatorResult {
  laptop_price_incl_warranty_usd: number | null;
  taxes_usd: number | null;
  shipping_usd: number | null;
  laptop_base_reimbursed_usd: number | null;
  tax_reimbursed_usd: number | null;
  canonical_reimbursed_usd: number | null;
  total_purchase_usd: number | null;
  employee_own_expense_usd: number | null;
  has_missing_inputs: boolean;
}

export interface ComplianceResult {
  cpu_pass: boolean | null;
  disk_pass: boolean | null;
  ram_pass: boolean | null;
  price_pass: boolean | null;
  warranty_pass: boolean | null;
}

export interface QuoteOverrides {
  currency_override?: string | null;
  price_override_local?: string | null;
  includes_tax?: boolean | null;
  includes_shipping?: boolean | null;
  includes_warranty?: boolean | null;
}

export interface InterpretQuoteResponse {
  interpretation_id: string;
  fields: ExtractedLaptopFields;
  exchange_rate: ExchangeRateInfo;
  pricing: PricingCalculatorResult;
  compliance: ComplianceResult;
  processed_image_url: string | null;
  processed_image_urls: string[];
  evidence_preview_url: string;
  preliminary: boolean;
  actual_purchase_is_authoritative: boolean;
  actual_purchase_is_authoritative_text: string;
  requested_overrides?: QuoteOverrides | null;
}

export interface AcceptQuoteRequest {
  folder_id?: string | null;
  overrides?: QuoteOverrides | null;
}

export interface AcceptQuoteResponse {
  evidence_filename: string;
  download_url: string;
}

// Purchase Details (section 4.3)

export interface ParsedTransaction {
  email: string;
  amount_signed: number;
  currency: string;
  date: string;
}

export interface PurchaseSummary {
  purchase_date: string;
  window_end_date: string;
  next_refresh_date: string;
  currency: string;
  net_amount_local: number;
  net_amount_usd: number | null;
  exchange_rate_local_per_usd: number | null;
  current_depreciated_value_local: number;
  current_depreciated_value_usd: number | null;
  anomalies: string[];
  transactions: ParsedTransaction[];
}

export interface PurchaseDetailsResponse {
  employee_email: string;
  purchases: PurchaseSummary[];
}

export interface PurchaseEligibilityResponse {
  employee_email: string;
  eligible_for_new_laptop: boolean;
  latest_purchase_date: string | null;
  next_planned_laptop_refresh: string | null;
  writeoff_months: number;
}

export interface EmployeePurchaseRow {
  employee_email: string;
  latest_purchase_date: string;
}

export interface EmployeesPurchaseListResponse {
  total_employees: number;
  employees: EmployeePurchaseRow[];
}
