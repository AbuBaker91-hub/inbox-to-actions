# Sample inbox

12 email files (`.txt` and `.eml`, parsed identically) plus 3 real PDF
agreements referenced via the `X-Attachment` header. Processing all of them
yields: **5 written, 3 in review, 4 skipped** and **5 contacts**.

| File | Category | Expected outcome |
|---|---|---|
| `01-lead-sarah.txt` | lead (0.95) | **written**: contact Sarah Chen, deal RIV-2031 (stage `new`), activity |
| `02-lead-michael.txt` | lead (0.92) | **written**: contact Michael Okafor, no reference so no deal, activity |
| `03-doc-riverside.txt` + `agreement-riverside-riv2031.pdf` | document (0.90) | **written**: contact (sender, Riverside Holdings LLC), deal RIV-2031 upserted to stage `agreement` with amount 450000 and 4 ordered key dates, activity |
| `04-lead-phone-typo.txt` | lead (0.90) | **review**, reason `validation`: phone `5551-02` has only 6 digits |
| `05-doc-oakwood.txt` + `agreement-oakwood-oak1189.pdf` | document (0.93) | **written**: contact (sender), deal OAK-1189 amount 275000, activity |
| `06-status-inspection.eml` | status_update (0.90) | **skipped**: no CRM write |
| `07-doc-pinehill-baddates.txt` + `agreement-pinehill-pin7742.pdf` | document (0.91) | **review**, reason `date_order`: the PDF states closing 2026-09-05 *before* acceptance 2026-10-01 |
| `08-other-newsletter.txt` | other (0.90) | **skipped** |
| `09-lead-fatima.txt` | lead (0.88) | **written**: contact Fatima Al-Rashid, deal MAP-3307, activity |
| `10-status-funds.eml` | status_update (0.92) | **skipped** |
| `11-other-vendor.txt` | other (0.95) | **skipped** |
| `12-lead-ambiguous.txt` | lead (0.55) | **review**, reason `low_confidence`: classifier confidence below 0.8 |

After a full run:

- `GET /emails` -> 12 rows
- `GET /review` -> 3 pending items (typo lead, bad-dates document, ambiguous lead)
- `GET /crm/contacts` -> 5 contacts (Sarah, Michael, Riverside sender, Oakwood sender, Fatima)
- `GET /crm/deals` -> 3 deals (RIV-2031, OAK-1189, MAP-3307)

The PDFs are generated once by `scripts/gen_sample_pdfs.py` (fpdf2) and
committed, so the repo works offline. Their text is what `pypdf` extracts at
ingest time; the Pine Hill one intentionally has its dates out of order.
