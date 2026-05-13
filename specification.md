## Staff Portal Specification

### 1. Purpose
Build a staff portal for the corporate laptop purchase process.

The product includes four core functionality pages:
1. Laptop Quote Registration page: register and verify a quote, then archive approved evidence in Google Drive.
2. Laptop Purchase Details page: show an individual employee's laptop purchase history and status.
3. Purchase Management Overview page: show all employees with links to each employee details page.
4. Onboarding page: list employees who are eligible for a laptop purchase and manage onboarding exports.

### 2. Project Structure
- staff_portal is the project root.
- backend contains a FastAPI application.
- frontend contains a TypeScript web application.
- Backend serves frontend public files.
- Backend API routes are namespaced under /api.
- testdata contains sample quote input files used for integration tests.

#### 2.1 Test Data
- Quote interpretation integration tests must read files from `testdata/`.
- Files in `testdata/` are representative shopping-cart examples for `/api/new_laptop` interpretation.
- Integration tests should validate that OpenRouter interpretation returns the required extraction fields for each test input.

### 3. Shared Platform Requirements

#### 3.1 Authentication and Access Control
- Authentication is required for application usage.
- Authentication provider is Google OIDC (Google Sign-In for a registered Google app).
- If a user is not authenticated, the user must be redirected to /login.
- Login page must allow Google sign-in.
- Only users with canonical.com email addresses are authorized.
- User email must be available to backend processing and rendered in generated evidence output.

#### 3.2 Common Look and Feel
- All pages must share a consistent visual style.
- A single shared CSS file must be used across all pages.
- The design system baseline is Vanilla Framework, following https://vanillaframework.io/ guidelines.
- Vanilla Framework patterns, spacing, typography, and components should be used consistently across all pages.
- Custom overrides or extensions should be placed in one shared stylesheet and imported consistently.
- No page-specific inline styles that duplicate or contradict the shared stylesheet.

#### 3.3 Configuration
Environment-based configuration is required for at least:
- Google Sign-In client id.
- OpenRouter API key and model.
- Session secret.
- Google Drive credentials and target folder.
- Laptop requirement thresholds.

### 4. Functionality Pages

#### 4.1 Login Page
Path:
- /login

Purpose:
- Authenticate user with Google before allowing access to any protected page.

Requirements:
- Show Google sign-in button and login prompt.
- Complete OIDC login flow for registered Google app.
- Enforce canonical.com domain authorization.
- On successful login, redirect to the default landing page.
- On failed login, show clear error state.

#### 4.2 Laptop Quote Registration Page
Path:
- New Laptop page

Purpose:
- Register, verify, and optionally archive a laptop quote from a shopping cart screenshot.

Quote approval process:
1. User uploads source file (image or PDF).
2. Backend processes/interprets/verifies content and generates evidence PDF.
3. User reviews extracted values — including detected currency — and submits; on submit, backend uploads PDF to Google Drive.
4. If the detected currency is wrong, user enters the correct currency code and resubmits. Backend re-interprets using the overridden currency and generates a new evidence PDF.

Frontend requirements:
- User can paste an image from clipboard (PNG or JPEG).
- User can select an image or PDF file (PNG, JPEG or PDF).
- PDF upload exists for cases where shopping cart content cannot be captured as a screenshot and the user prints the cart to PDF.
- User submits image to backend.
- Page displays processed PDF preview and extracted/interpreted values.
- Detected currency is shown prominently as part of the extracted values the user must review.
- An optional currency override field (small free-text input, e.g. "USD", "SEK") is shown alongside the detected currency.
- If the user enters a currency override and resubmits, the backend re-interprets using the supplied currency and returns a fresh evidence PDF.
- Quote acceptance page must include a pricing calculator that shows Canonical reimbursement and employee own expense.
- Quote acceptance page must clearly label interpretation and calculator output as preliminary purchase interpretation.
- Quote acceptance page must display text that the actual purchase is the authoritative record and determines final outcomes.
- Quote acceptance page must include a simple `Submit` action.
- Page displays compliance outcomes.
- User can submit without any acknowledgement checkboxes.
- After submit succeeds, the user must be shown a link to the generated evidence file in Google Drive.
- The success UI must include a `Copy link` action that copies the evidence file URL to clipboard.

Backend requirements:
- Provide API flow under /api/new_laptop.
- Accept uploaded screenshot image or PDF.
- For PDFs, extract and process multiple pages as the evidence source for interpretation and rendering.
- For multi-page PDFs, preserve page order in generated evidence output.
- Send source content to OpenRouter for quote interpretation.
- OpenRouter model choice must be configurable by environment variable.
- Default model should be `google/gemini-2.5-flash` unless explicitly overridden.

Model extraction requirements:
- CPU core count, directly or inferred through CPU model.
- Disk amount in GB.
- RAM amount in GB.
- Laptop cost excluding taxes and shipping.
- Laptop price including warranty (required for reimbursement calculation).
- Warranty term in years.
- Taxes charged.
- Shipping charged.
- Detected currency.

Pricing calculator requirements (quote acceptance page):
- Calculator must run on the quote page before approval and show all intermediate values.
- Maximum reimbursable laptop base is 2900 USD.
- Inputs (USD):
  - Laptop price including warranty.
  - Taxes charged.
  - Shipping charged.
- Shipping must be clearly stated on the shopping cart and parsed separately.
- Calculation rules:
  - `laptop_base_reimbursed_usd = min(2900, laptop_price_including_warranty_usd)`
  - `tax_reimbursed_usd = (laptop_base_reimbursed_usd / laptop_price_including_warranty_usd) * taxes_usd`
  - `canonical_reimbursed_usd = laptop_base_reimbursed_usd + shipping_usd + tax_reimbursed_usd`
  - `total_purchase_usd = laptop_price_including_warranty_usd + taxes_usd + shipping_usd`
  - `employee_own_expense_usd = total_purchase_usd - canonical_reimbursed_usd`
- The calculator must show both:
  - Canonical reimbursed amount (USD).
  - Employee own expense amount (USD).
- Values should be displayed rounded to 2 decimals.
- If any required input value is missing or unparseable, show a clear warning and allow user submission because interpretation is preliminary.

Multilingual and currency requirements:
- Screenshot language may be any language.
- Currency must be interpreted from screenshot context.
- The model response must return the detected currency code explicitly (e.g. "USD", "SEK"); this is a required field in the interpretation response.
- If the user supplies a currency override, that value takes precedence over the model-detected currency and the backend must re-run interpretation with the override applied.
- Price must be shown in local currency and USD.
- USD conversion must use the current Frankfurter API exchange rate at quote interpretation/approval time.
- No historical exchange-rate lookup is required.
- The exact exchange rate used must be shown.

Compliance requirements:
- Evaluate extracted values against configured thresholds.
- Include pass/fail for CPU, disk, RAM, price, and warranty.
- Warranty compliance rule: warranty must be at least 3 years.

Privacy and evidence generation requirements:
- PII in source image/PDF must be blurred before evidence PDF generation.
- OpenRouter-routed model calls are used to perform PII detection for blurring (for image input, directly; for PDF input, per converted page image).
- For PDF input, convert each page to an image first, run model-driven PII blurring per page, and use the blurred pages in evidence rendering.
- Generate derived evidence as PDF (always PDF output).
- Implementation is intentionally simple: convert input to image(s), place image(s) at top of PDF page(s) scaled to fit width, then render a table of interpreted values below. No complex layout engine is needed.
- For PDFs with multiple pages, each page becomes one blurred image placed on its own PDF page, followed by the interpretation table on the final page.
- Use `pdf2image` or `pymupdf` to convert PDF pages to images; use `reportlab` or `fpdf2` for PDF assembly.
- Evidence PDF layout should contain the source screenshot/page at top and a white footer/content section below.
- Footer/content section must include:
  - Timestamp.
  - Interpreted CPU details.
  - CPU specification pass/fail indication.
  - Interpreted warranty term.
  - Warranty pass/fail indication (minimum 3 years).
  - User email address.
- Footer/content section should also include other interpreted hardware/price values and pass/fail states.
- Footer/content section must include the exchange rate captured at interpretation/approval time.
- Footer/content section must include text stating interpretation and calculator output are preliminary and that the actual purchase is authoritative.

Acceptance and archive requirements:
- Show processed evidence PDF to user for review.
- On submit, upload processed evidence PDF to Google Drive.
- Evidence PDF filename schema must be `<YYYY-MM-DD-THH:MM:SS:mmmZ>-<email>-laptop-quote.pdf` using UTC timestamp with milliseconds.
- Save the original uploaded input file to a separate configurable Google Drive folder for quote inputs.
- Input archive filename must use the same base name as the evidence file, with `-laptop-quote-input` before the extension while preserving original input extension (for example: `.png`, `.jpeg`, `.pdf`).
- Input archive filename example: `<YYYY-MM-DD-THH:MM:SS:mmmZ>-<email>-laptop-quote-input.png`.
- Destination folder is configurable.
- Store under user-specific folder/namespace based on authenticated user email.

Output contract:
- Return extracted laptop fields.
- Return extracted warranty term in years.
- Return currency and exchange-rate details.
- Return compliance decisions.
- Return preliminary status flag for interpretation/calculator output.
- Return `actual_purchase_is_authoritative` flag and display text.
- Return pricing calculator inputs and outputs (USD): laptop price including warranty, taxes, shipping, reimbursement breakdown, total purchase, and employee own expense.
- Return reference to processed evidence PDF.
- Return Drive link/URL for the generated evidence PDF suitable for presenting to the user.
- Return copyable evidence link text/value for clipboard action.
- Do not return any link/reference to the archived original input file.
- Return identifier or endpoint for submit and Drive upload action.

#### 4.3 Laptop Purchase Details Page
Purpose:
- Show a single employee's laptop purchase information and purchase status.

Requirements:
- Display employee identity and current laptop purchase state.
- Display interpreted laptop purchases derived from approved expense data for the staff member.
- Multiple expense transactions may map to one laptop purchase, based on business grouping rules.
- Candidate grouping rule: transactions within 14 days may be treated as one purchase; additional grouping logic may apply for longer timelines.
- Display all related expenses for manual review and auditing.
- Preferred UI is a summary list of interpreted purchases with expandable panels that show all underlying transactions.
- Display registered quote outcomes and linked evidence where available.
- If only indirect evidence exists (for example, approximate matching by amount/date), display that relationship clearly.
- Display final approved purchase details.
- Display current depreciated value per purchase, using a 3-year linear write-off starting from interpreted purchase date.
- Be reachable from management overview links.

Expense interpretation logic (based on available expense dataset columns):
- Input columns expected: Employee e-mail, Date, Currency, Amount, Process, Reference, Comment.
- Primary grouping key: Employee e-mail.
- Parse Amount as signed numeric value (supports values like "$2,598", "$132", "-$113").
- Transactions with positive amounts contribute to purchase value.
- Transactions with negative amounts represent refunds/credits and reduce grouped purchase value.
- Candidate purchase window: 14 calendar days from first transaction in the group.
- Grouping algorithm per employee:
  - Sort transactions by Date ascending.
  - Start a new purchase group at first unassigned transaction.
  - Include later transactions within 14 days into same group.
  - Net purchase amount = sum of signed Amount across grouped transactions.
- Outlier handling:
  - If net purchase amount <= 0, mark group as anomaly for manual review.
  - If net purchase amount is unusually high (for example > 1.7x configured max laptop price), mark as potential multi-item bundle.
- Purchase date for depreciation and eligibility cadence is interpreted purchase date:
  - default to earliest transaction date in the grouped purchase.
- Currency recording:
  - Record local currency amount for each transaction and for group totals.
  - Record USD amount for each transaction and for group totals.
  - Record exchange rate captured at quote interpretation/approval time.

#### 4.4 Purchase Management Overview Page
Purpose:
- Provide management overview across all employees' laptop purchases.

Requirements:
- List employees and current purchase status.
- Not all purchases may be automatically interpreted; unresolved cases should be visible.
- Provide links to each employee Purchase Details page.
- Support at least basic filtering/sorting by status and staff e-mail.
- Scale target is approximately 2,000 to 4,000 staff members.
- Provide a direct link to the backing Google Drive folder for manual operations.

#### 4.5 Onboarding Page
Path:
- /onboarding

Purpose:
- Show employees currently eligible for laptop purchase.

Requirements:
- List eligible employees based on defined policy/rules.
- Eligibility policy:
  - Every employee can receive a new laptop every 3 years.
  - New employees are eligible when current date is after their first day of employment.
  - CSV generation should be simple and use UTC day boundaries.
  - If a CSV is generated today, it should include employees eligible up to and including yesterday in UTC.
  - Do not include employees first added today in UTC in today's generated CSV.
  - Employees first added today in UTC should instead be considered in the next CSV generation.
  - Staff members who are otherwise eligible but missing required contact or address data must be added to a waiting list.
- Employee source is current employees in HRc.
- Reference logic exists in ../hr-onboarding/src/generate_expensify_csv.py.
- User must have a valid phone number and a valid address. If not, they have to be put on the waiting list.
- Provide a Generate CSV button.
- On click, write currently eligible employees to CSV.
- If some users previously came from the waiting list and are now included in the generated CSV, remove them from the waiting list.
- Save generated CSV files to a dedicated Google Drive folder.
- Keep the waiting list in the same Google Drive area, in a dedicated sheet or file that is visible to operators.
- List generated CSV files in the lower section of the page from Google Drive directory listing.
- Generated CSV files must be sorted by filename in descending order.
- In the CSV list, the filename itself must be rendered as a clickable link that downloads the file.
- Each CSV has a lifecycle status: Generated, Submitted, Processed.
- Status may be encoded in filename.
- Filename must follow the pattern expensify-YYYY-MM-DD-<Status>.csv.
- <Status> must align with lifecycle status values (Generated, Submitted, Processed).
- Provide a status-change action (rename-based if status is filename-encoded).
- Require explicit user confirmation before status change.
- Status changes may move both forward and backward to correct erroneous actions.
- If status changes to Processed, send instruction emails to staff members listed in the CSV.
- Emails must be generated from a template.

### 5. Non-Goals for Initial Version
- No manual post-processing editor before acceptance.
- No alternate auth providers besides Google.
- No charm packaging in the initial development phase (localhost first).

### 6. Engineering Standards
- Python dependencies are managed via `pyproject.toml` at the `staff_portal` root. No `requirements.txt` files.
- Dev/test dependencies are declared under `[project.optional-dependencies] dev`.
- Model API integrations for Workstream A must use OpenRouter.
- Code should be well structured; avoid duplicated constants/strings.
- Business logic should be implemented once per layer and reused.
- Interpretation of approved expenses into grouped laptop purchases should be implemented in a dedicated backend module/class and reused across backend features.
- Frontend should consume interpreted purchase data from backend, not duplicate the grouping logic.
- Frontend architecture and static asset delivery:
  - HTML entry files are build artifacts placed in the frontend `public` output.
  - HTML must reference fingerprinted JavaScript and CSS bundles (content-hashed filenames) rather than non-versioned asset names.
  - Script and stylesheet tags in generated HTML must include integrity checksums so the browser verifies asset consistency.
  - Backend should serve these built `public` artifacts as-is; runtime should not rewrite asset filenames.
  - Build/deploy must always publish HTML and hashed assets from the same build to avoid mismatch between HTML references and bundle files.
- Input validation should exist in both frontend and backend.
- Unit tests are required in frontend and backend with a target of 80% coverage.
- External service usage in tests:
  - AI API calls may use real service.
  - Google Drive writes should use test folders.
  - Google Drive reads (approved expenses) may use real documents.
- Lessons from implementation feedback should be captured and applied consistently in future work.

### 7. Hackathon Scope

Development is split into a pre-hackathon preparation phase and the hackathon day itself.

#### 7.1 Pre-Hackathon Phase
The following work is completed before the hackathon day so that the hackathon can focus on business logic rather than plumbing.

**Authentication:**
- Full Google OIDC wiring: login page, callback handler, session management, canonical.com domain enforcement.
- Shared CSS stylesheet and Vanilla Framework integration (Step 0 foundations).

**Bootstrap tool:**
- Implement the Bootstrap CLI tool (section 11).
- Provision GCP project, OAuth credentials, Drive folders (quotes test + quotes production), and any required service accounts.
- Drive folders for quotes (test and production environments) must be created and folder IDs recorded in `.env` before the hackathon starts.

**Vault integration:**
- Implement the Vault secret loading layer in the backend.
- Reference implementation exists in `hr-onboarding/src/common.py` (`load_hrc_secrets`): uses `hvac` client, `VAULT_TOKEN` environment variable, and path-based secret read from `vault.ps7.admin.canonical.com`.
- Adapt this pattern for the staff portal's secret path and secret set.
- All required secrets loaded and confirmed working before the hackathon day.

**Workstream C — Onboarding:**
- Eligibility evaluation logic.
- CSV generation and Drive upload.
- Waiting list management.
- CSV lifecycle status management (Generated → Submitted → Processed, bidirectional).
- The Onboarding page UI.
- Email sending is explicitly excluded (post-hackathon).

**API contracts:**
- Define field-level schemas for all workstream contracts before the hackathon day.

#### 7.2 Hackathon Day
With plumbing and Onboarding workstream complete, the hackathon focuses on:

**Primary target — Workstream A (Quote registration):**
- Upload image or PDF.
- OpenRouter-driven interpretation and compliance evaluation.
- Evidence PDF generation.
- Evidence review and Drive archive on approval.

**Stretch target — Workstream B (Purchase tracking):**
- Expense grouping logic.
- Purchase details page.
- Management overview page.

**Test strategy:**
- The 80% coverage target is dropped.
- Unit tests are used for rapid iteration: write a test to invoke and debug a function directly rather than exercising the full application workflow. Write the test first, make the function work, then move on.
- Tests that already exist must remain passing.

### 8. Delivery Approach
- Development should be parallelized with multiple agents where practical.
- Work should follow a contract-first approach between frontend and backend.

**Step 0 — Shared foundations (pre-hackathon, blocking for all other work):**
- Define and implement the shared CSS stylesheet and Vanilla Framework integration.
- Establish authentication wiring (login page, OIDC callback, session handling).
- Complete Vault integration and Bootstrap tool.
- Complete Workstream C (Onboarding).
- All other work depends on these being in place.

**Step 1 — Define API contracts per workstream.**

See section 13 for the entity and endpoint listing. Field-level schema is defined in a separate API contract document.

**Step 2 — Parallel workstreams (each independently assignable):**

- **Workstream A — Quote verification:**
  Interpret uploaded quote and generate evidence PDF; accept and archive to Drive.
  This workstream is fully independent from purchase tracking and eligibility.

- **Workstream B — Purchase tracking:**
  Expense grouping, purchase history, purchase details page, and management overview.

- **Workstream C — Onboarding:**
  Eligibility evaluation, waiting list, CSV generation, lifecycle status management, and instruction emails.

Frontend and backend for each workstream can be developed in parallel once the contract is defined.

Integration work should validate that both implementations conform to the agreed contract.

### 9. Target Deployment: 12-Factor Charm
The end goal is to deliver this application as a [12-factor app](https://12factor.net/) packaged as a Juju charm.

During initial development the application runs on localhost. The 12-factor constraints should be respected from the start so that the charm packaging step is straightforward rather than a rewrite.

Implications for development:
- All configuration must come from environment variables (no config baked into code).
- No local filesystem state; all persistent data lives in external services (Google Drive, Vault).
- The application must be stateless across requests; session state is carried in signed cookies or tokens only.
- Logging must go to stdout/stderr; no file-based log management in the application layer.
- The application must bind to a port supplied by the environment (`PORT` variable or equivalent).
- Backing services (Drive, Vault, OpenRouter) are attached via configuration, not hard-coded addresses.
- There must be a clean separation between build, release, and run stages; the pyproject.toml build system supports this.

### 10. Documentation
- All pages should include sufficient user-facing instructions.
- Write a README.md that introduces the project, architecture, setup, configuration, and operational flows.
- Keep README.md up to date with implementation changes.

### 11. Bootstrap
Write a separate Python bootstrap tool to provision and configure the Google-side resources needed by the application. The bootstrap should be run from a command-line, no GUI is needed.

Bootstrap requirements:
- Input should include at minimum:
  1. A Google Cloud project identifier.
  2. Any application-specific configuration values required for resource creation, except OpenRouter API keys.
- Assume the operator is already logged in with gcloud.
- Use Google APIs as much as possible.
- Use gcloud only as an authentication/token bootstrap when necessary.
- OpenRouter API keys must not be bootstrapped; they will be provided separately.
- Bootstrap output should clearly report what resources were created, configured, skipped, or require manual follow-up.
- Bootstrap should be safe to re-run and should avoid duplicating already-created resources when possible.
- Bootstrap should not generate any documents in Google Drive.
- Bootstrap should read the .env file.
- Bootstrap should report any required environment variables that are unset.
- If bootstrap has enough information to suggest values for missing environment variables, it should prompt the operator to add them to .env.
- Bootstrap should check for any required secrets missing from Vault.
- If secrets are missing, bootstrap should prompt the operator to add them.
- If bootstrap generates secret values during setup, it should display them to the operator so they can be stored in Vault and/or .env as appropriate.
- Bootstrap should clearly distinguish between:
  - values that belong in .env
  - values that belong in Vault
  - values that require manual operator action outside the bootstrap tool

### 12. Secret management
- All secrets should be stored in HashiCorp Vault.
- Access tokens required to reach Vault or cloud APIs may be assumed to be available in environment variables.
- If required access tokens are missing from the environment, the operator should be prompted clearly.
- The system should avoid storing long-lived secrets directly in source code or committed files.
- Secret ownership should be explicit:
  - application secrets belong in Vault
  - local developer/runtime configuration belongs in .env when appropriate
- Documentation should describe which values are expected in Vault and which are expected in .env.
- Expected Vault-managed secrets include:
  - Google OAuth secrets
  - service account credentials, if service accounts are needed
  - API keys
  - other application secrets such as session secrets
- Non-secret configuration should not be stored in Vault when it is better represented as normal configuration.
- Examples of values that do not need to be stored in Vault:
  - Google Drive folder or file identifiers
  - minimum laptop specification thresholds
  - other non-secret application settings

### 13. Coding Assistant Guidance

Extracted to `.github/copilot-instructions.md` at the repository root. That file is automatically loaded by every Copilot agent session and is the authoritative location for assistant guidance and implementation conclusions.

### 14. API Contract Summary

The following entities and endpoints are required by the frontend. Field-level schema is defined separately in the API contract document.

**Authentication and configuration**
- `GET /api/config` — client-side configuration (Google client ID)
- `GET /api/me` — authenticated user identity
- `GET /api/auth/callback` — OIDC callback handler
- `POST /api/auth/logout` — logout and session teardown

**Quote registration (Workstream A)**
- `POST /api/new_laptop/interpret` — upload image or PDF; performs OpenRouter-driven PII blurring and interpretation, then returns interpreted quote (including warranty term), compliance result (including warranty pass/fail), pricing calculator inputs/outputs, preliminary-status indicators, and evidence PDF reference
- `POST /api/new_laptop/submit` — submit interpreted result, upload evidence PDF and original input file to their respective Drive folders, and return evidence Drive link for user display/copy

**Purchase tracking (Workstream B)**
- `GET /api/employees` — list all employees with purchase summary and status (management overview)
- `GET /api/employees/{email}` — single employee identity and current purchase state
- `GET /api/employees/{email}/purchases` — interpreted and grouped laptop purchases
- `GET /api/employees/{email}/expenses` — raw expense transactions
- `GET /api/employees/{email}/quotes` — registered quote records and evidence links

**Onboarding (Workstream C)**
- `GET /api/onboarding/eligible` — list currently eligible employees, including waiting list status
- `POST /api/onboarding/csv` — generate and store a new eligible employees CSV
- `GET /api/onboarding/csvs` — list generated CSV files from Drive
- `PATCH /api/onboarding/csvs/{id}/status` — change lifecycle status of a CSV (Generated, Submitted, Processed; bidirectional)