"""One-off generator for the three sample agreement PDFs (fpdf2, dev extra).

Run once from the repo root and commit the output:

    python scripts/gen_sample_pdfs.py

The Pine Hill agreement intentionally states its dates OUT OF ORDER
(closing before acceptance) so the pipeline's date_order guardrail fires.
"""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "samples" / "inbox"


def build(filename: str, title: str, lines: list[str]) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    for line in lines:
        pdf.multi_cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(OUT / filename))
    print(f"wrote {OUT / filename}")


build(
    "agreement-riverside-riv2031.pdf",
    "PURCHASE AGREEMENT - Reference RIV-2031",
    [
        "This Purchase Agreement (Reference: RIV-2031) is entered into between "
        "Riverside Holdings LLC (Seller) and Chen Family Trust (Buyer).",
        "Purchase Price: $450,000.00",
        "Earnest Money Deposit: $5,000.00",
        "Acceptance Date: 2026-09-01",
        "Earnest Money Due Date: 2026-09-04",
        "Due Diligence Deadline: 2026-09-15",
        "Closing Date: 2026-10-01",
        "The parties agree to the milestones above. Executed in duplicate.",
    ],
)

build(
    "agreement-oakwood-oak1189.pdf",
    "PURCHASE AND SALE AGREEMENT - Reference OAK-1189",
    [
        "This Purchase and Sale Agreement (Reference: OAK-1189) is made between "
        "Oakwood Ventures LP (Seller) and Gonzalez Properties Inc (Buyer).",
        "Purchase Price: $275,000.00",
        "Acceptance Date: 2026-08-20",
        "Earnest Money Due Date: 2026-08-24",
        "Due Diligence Deadline: 2026-09-05",
        "Closing Date: 2026-09-30",
        "Time is of the essence for each date stated above.",
    ],
)

build(
    "agreement-pinehill-pin7742.pdf",
    "AGREEMENT - Reference PIN-7742",
    [
        "This Agreement (Reference: PIN-7742) is made between Pine Hill Group "
        "(Seller) and Marsh & Sons LLC (Buyer).",
        "Purchase Price: $1,250,000.00",
        # Intentionally out of order: closing precedes acceptance.
        "Acceptance Date: 2026-10-01",
        "Earnest Money Due Date: 2026-10-05",
        "Due Diligence Deadline: 2026-09-20",
        "Closing Date: 2026-09-05",
        "Prepared in haste; parties to verify all dates before recording.",
    ],
)
