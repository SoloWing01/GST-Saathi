"""Generate sample GST notices for testing Phase 1.

Run once:
    cd backend && uv run python data/generate_samples.py

Creates three files in data/sample_notices/:
  1. sample_text.pdf      — text-based PDF notice
  2. sample_scanned.png   — image that looks like a scanned notice
  3. sample_pasted.txt    — plain text notice (content only, for paste mode)
"""

from __future__ import annotations

import os
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent / "sample_notices"


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    _create_text_pdf()
    _create_scanned_image()
    _create_pasted_text()
    print(f"Sample notices created in {SAMPLE_DIR}/")


def _create_text_pdf() -> None:
    """Create a text-based PDF GST notice using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    path = SAMPLE_DIR / "sample_text.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    y = height - 40 * mm
    lines = [
        "GOVERNMENT OF INDIA",
        "CENTRAL BOARD OF INDIRECT TAXES AND CUSTOMS",
        "",
        "NOTICE UNDER SECTION 61 OF THE CGST ACT, 2017",
        "",
        "Reference No: ASMT-10/2025-26/001234",
        "Date: 15-Jan-2025",
        "",
        "To:",
        "M/S QUICK COMMERCE PRIVATE LIMITED",
        "GSTIN: 27AABCU9603R1ZM",
        "Tax Period: April 2024 - June 2024 (Q1 FY 2024-25)",
        "",
        "Sir/Madam,",
        "",
        "It has been noticed from the analysis of your returns filed under",
        "the Goods and Services Tax that there are certain discrepancies",
        "in the details furnished by you in your returns vis-a-vis the",
        "details available on the portal.",
        "",
        "Specifically:",
        "1. Difference in outward supply details between GSTR-1 and GSTR-3B",
        "   Reported in GSTR-1:  Rs. 12,45,000",
        "   Reported in GSTR-3B: Rs. 11,80,000",
        "   Difference:           Rs.   65,000",
        "",
        "2. ITC claimed in GSTR-3B exceeds ITC available as per GSTR-2B",
        "   ITC as per GSTR-2B:  Rs. 1,85,000",
        "   ITC claimed GSTR-3B: Rs. 2,10,000",
        "   Excess ITC:          Rs.   25,000",
        "",
        "You are hereby called upon to show cause as to why an order",
        "demanding the above differential tax of Rs. 90,000 along with",
        "applicable interest and penalty should not be passed against you.",
        "",
        "You are requested to file your reply within 30 days of receipt",
        "of this notice, either electronically through the GST Common",
        "Portal or personally at the office of the undersigned.",
        "",
        "If you fail to reply within the stipulated time, the case will",
        "be decided ex-parte on the basis of available records.",
        "",
        "Yours faithfully,",
        "(Authorized Signatory)",
        "Superintendent (Anti-Evasion)",
        "Commissionerate: Mumbai South",
    ]

    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(25 * mm, y, line)
        y -= 5 * mm

    c.save()
    print(f"  Created {path.name} ({path.stat().st_size} bytes)")


def _create_scanned_image() -> None:
    """Create an image that looks like a scanned notice (white text on light background with noise)."""
    from PIL import Image, ImageDraw, ImageFont
    import random

    width, height = 800, 1100
    img = Image.new("RGB", (width, height), color=(248, 245, 240))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_bold = font

    lines = [
        ("NOTICE UNDER SECTION 73 OF THE CGST ACT, 2017", font_bold),
        ("", font),
        ("Reference: DRC-01/2025-26/005678", font),
        ("Date: 20-Feb-2025", font),
        ("", font),
        ("To:", font),
        ("M/S GREEN ENERGY SOLUTIONS", font),
        ("GSTIN: 06BBBFM1234N1Z5", font),
        ("Tax Period: October 2024 - December 2024 (Q3 FY 2024-25)", font),
        ("", font),
        ("This notice is issued under Section 73(1) of the CGST Act, 2017", font),
        ("for the tax period mentioned above.", font),
        ("", font),
        ("Brief of the case:", font),
        ("During the course of scrutiny of your returns, it was found that", font),
        ("you have availed Input Tax Credit (ITC) of Rs. 45,000 which is", font),
        ("not supported by valid invoices as per GSTR-2B auto-population.", font),
        ("", font),
        ("The details are as follows:", font),
        ("  ITC claimed in GSTR-3B:    Rs. 3,45,000", font),
        ("  ITC available in GSTR-2B:  Rs. 3,00,000", font),
        ("  Discrepancy:                Rs.    45,000", font),
        ("", font),
        ("You are called upon to show cause why the above amount of", font),
        ("Rs. 45,000 along with interest under Section 50 and applicable", font),
        ("penalty should not be demanded from you.", font),
        ("", font),
        ("Reply within 30 days.", font),
        ("", font),
        ("Deputy Commissioner", font),
        ("GST Commissionerate: Delhi East", font),
    ]

    y = 50
    for text, f in lines:
        # Add slight random offset for "scanned" look
        x_offset = random.randint(-1, 1)
        y_offset = random.randint(-1, 1)
        draw.text((40 + x_offset, y + y_offset), text, fill=(30, 30, 30), font=f)
        y += 28

    # Add some noise dots for realism
    for _ in range(200):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        gray = random.randint(180, 220)
        draw.point((x, y), fill=(gray, gray, gray))

    path = SAMPLE_DIR / "sample_scanned.png"
    img.save(path)
    print(f"  Created {path.name} ({path.stat().st_size} bytes)")


def _create_pasted_text() -> None:
    """Create a plain text sample notice."""
    content = """SHOW CAUSE NOTICE
Section 16(2)(d) of the CGST Act, 2017

Reference: REG-17/2025-26/009012
Date: 05-Mar-2025

To: M/S SUNRISE RETAILERS
GSTIN: 24CCCDR5678M1Z3
PAN: CCDR5678M

Subject: Denial of Input Tax Credit - Rule 36(4) violation

Dear Sir/Madam,

It has been noticed that you have availed Input Tax Credit in excess of
what is permissible under Rule 36(4) of the CGST Rules, 2018.

Details:
- Total ITC available in GSTR-2B: Rs. 5,20,000
- ITC claimed in GSTR-3B:         Rs. 5,85,000
- Excess ITC availed:             Rs.   65,000
- Tax period: September 2024

As per Rule 36(4), ITC claims cannot exceed 105% of the eligible credit
available in GSTR-2B. The excess amount of Rs. 65,000 is being denied.

You are directed to show cause within 30 days as to why:
1. The excess ITC of Rs. 65,000 should not be reversed
2. Interest under Section 50 should not be charged
3. Penalty under Section 122 should not be imposed

Failure to respond will result in ex-parte proceedings.

Assistant Commissioner
GST Division: Ahmedabad-I
"""
    path = SAMPLE_DIR / "sample_pasted.txt"
    path.write_text(content.strip())
    print(f"  Created {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
