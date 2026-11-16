# VeriQuay — Vendor Assurance

**A real, runnable procurement onboarding case-study application** (Zamp PS-2). Built on the previous VendorFlow AI project, retaining its SQLite decision engine, eight scenarios, and manual intake while adding live execution, more helpful communication, OCR support, and a redesigned UI.

> **Synthetic proof of concept.** Do not upload actual banking, tax, or identity documents. This app does **not** authenticate vendor identities, query government databases, verify bank ownership, or automatically send emails.

## Windows setup

1. Extract the ZIP into a new folder (do not run the app directly inside the ZIP).
2. Open PowerShell / VS Code terminal in the folder containing `app.py`.
3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

   If your Python 3.15 installation needs prerelease binary wheels, use the approach that worked for your previous Streamlit install:

   ```powershell
   python -m pip install --pre --only-binary=:all: -r requirements.txt
   ```

4. Launch:

   ```powershell
   python -m streamlit run app.py
   ```

5. Open the local URL shown in your terminal (usually `http://localhost:8501`).

If the old app is running, stop it with `Ctrl+C` before launching this one, or Streamlit may choose another port. Python 3.11–3.13 are also suitable alternatives if some Python 3.15 dependency wheels are unavailable.

## Scanned PDF OCR — optional additional setup

The app can read ordinary text PDFs with PyMuPDF without any extra software. For **scanned/image-only PDFs**, it uses **pytesseract + Pillow** (included in `requirements.txt`) and also needs the **Tesseract OCR executable** installed separately on Windows.

- Install Tesseract OCR for Windows from a trusted distribution, and add its installation directory to your system `PATH`.
- Close and reopen the terminal; run `tesseract --version` to confirm the executable is accessible.
- Restart Streamlit. On the **Document evidence** tab, look for `Extraction: OCR` after uploading a readable scanned PDF.
- If OCR is missing or fails, the application will flag the document for human review instead of pretending to have verified it.

OCR is best-effort: very poor scans, rotated pages, unusual templates, and handwritten content can still fail. It is **not** official document verification.

## Main pages

| Page | Purpose |
|---|---|
| Command center | KPI cards, status filters, recent runs, vendor registry |
| Live workflow | Execute eight reproducible scenarios with a **live stage stream** |
| Vendor intake | Submit new vendor or update existing record, with optional supporting PDF |
| Decision explorer | Inspect saved validation decisions, reasons, and bank-change alerts |
| Policy & scope | Decision rules, privacy notes, limitations |

## What changed from VendorFlow AI

1. **Actual stage callbacks** — the UI updates as ingestion, PDF extraction, each validation check, and database commit happen. There is a small deliberate display delay for readability; the stages are real.
2. **Action routing** — the resolution plan separates vendor requests from internal procurement work. Duplicate detection and bank changes are internal review tasks; mismatched PDFs request corrections. Rejection emails no longer incorrectly say `Pending`.
3. **Flexible document extraction** — multiple field labels and several date formats are supported. The evidence view displays extracted fields, source snippets, comparison outcomes, missing fields, and coverage.
4. **Optional OCR** — Tesseract can extract labeled fields from scanned PDFs when installed; if unavailable, the system safely requests review.
5. **Redesigned Streamlit UI** — a distinct VeriQuay visual identity, live workflow, interactive history filtering, decision dossier tabs, evidence comparison, and downloadable outputs.

## Demo scenarios

| Scenario | Expected status | Why |
|---|---|---|
| 01 Happy path | Approved | Matching form and PDF, no flags |
| 02 Bank switch | Pending | Existing vendor's account changed; independent verification |
| 03 Duplicate identity | Pending | Same tax fingerprint appears in another vendor record |
| 04 Expired certificate | Pending | Expiry date is in the past |
| 05 Subsidiary mismatch | Pending | Parent/affiliate account holder requires independent review |
| 06 PDF tax mismatch | Pending | Form tax ID differs from document |
| 07 Confirmed disqualification | Rejected | **Explicit fictional** internal policy block |
| 08 Unreadable PDF | Pending | No supported labeled fields could be extracted |

**Important:** Scenarios use a shared local database. Repeatedly running the same happy path can create duplicates and therefore turn a later Happy Path run into `Pending`. For a pristine demonstration, stop Streamlit, back up or delete the generated `vendorflow.db` file in the new folder, then restart. This resets only demo history in that folder.

## Tests

```powershell
python -m unittest discover -v
```

## Suggested five-minute demo

- **0:00–0:40** — Problem, VeriQuay Command center, and intended procurement user.
- **0:40–1:30** — Live workflow Happy path, show stages as they execute, Approved result.
- **1:30–2:25** — PDF tax mismatch, side-by-side document vs. form, vendor correction draft.
- **2:25–3:15** — Bank switch, internal verification task, audit event.
- **3:15–4:00** — Duplicate identity or expired certificate, show safe Pending decision.
- **4:00–4:35** — Decision explorer and history; show traceability.
- **4:35–5:00** — Explain that OCR is optional, decisions are deterministic, and human review protects ambiguous cases.

## Architecture

- `app.py` — Streamlit UI and live stage updates
- `workflow.py` — orchestration and document processing
- `document_intelligence.py` — PDF text/OCR extraction and field comparisons
- `engine.py` — deterministic validation, persistence, communication plan
- `scenarios.py` — fictional input and PDF generation
- `test_final.py`, `test_enhancements.py` — integration tests
- `sample_documents/` — eight synthetic scenario PDFs plus `ocr_scanned_example.pdf` (image-only sample for testing OCR)

## Scope and security

This is a demo, not production procurement infrastructure. No authentication or role-based access control, no encryption-at-rest, no secure multi-tenant separation, no official GSTIN/bank checks, no email delivery, and no certificate authenticity verification. SQLite is local; ephemeral cloud hosting may lose data. Tax IDs and bank account numbers are fingerprinted or masked in stored vendor records. Uploaded PDFs are processed in memory and not retained.
