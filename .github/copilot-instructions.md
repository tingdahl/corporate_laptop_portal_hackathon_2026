# Copilot Repository Instructions

These instructions are automatically read by GitHub Copilot for this repository.

## Default behavior

- Read `specification.md` before proposing or implementing changes.
- Prefer minimal, focused diffs that preserve existing architecture and naming.
- For backend changes, keep FastAPI route contracts and `contracts/` models aligned.
- For frontend changes, keep `templates/` and `frontend/` entrypoints consistent.
- Do not modify generated assets in `frontend/public/assets/` unless explicitly requested.
- Run relevant checks or tests for changed areas when possible.
- Call out assumptions and potential regressions in the final summary.

## Security and data handling

- Avoid logging secrets, tokens, cookies, or personally identifiable information.
- Keep security-related behavior in `backend/security_headers.py` intact unless asked to change it.
- Follow least-privilege patterns for Google Drive and Google Sheets integrations.