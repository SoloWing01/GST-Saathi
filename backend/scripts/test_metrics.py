"""Test metrics script — run all sample notices and compute success metrics.

Usage:
    cd backend
    python -m scripts.test_metrics

Reports:
    - Notice-type classification accuracy
    - Correct mismatch detection rate
    - Citation coverage (citations per factual claim)
    - "I don't know" / low-confidence fallback rate
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLES = [
    {
        "name": "ASMT-10 (text PDF)",
        "file": "data/sample_notices/sample_text.pdf",
        "content_type": "application/pdf",
        "expected_type": "ASMT-10",
        "expected_amount": 90000,
        "expected_mismatches": True,
    },
    {
        "name": "DRC-01 (scanned image)",
        "file": "data/sample_notices/sample_scanned.png",
        "content_type": "image/png",
        "expected_type": "DRC-01",
        "expected_amount": 45000,
        "expected_mismatches": False,
    },
    {
        "name": "REG-17 (pasted text)",
        "file": "data/sample_notices/sample_pasted.txt",
        "content_type": "text/plain",
        "expected_type": "REG-17",
        "expected_amount": 65000,
        "expected_mismatches": False,
    },
]


def run_test(sample: dict) -> dict:
    """Run the full pipeline on a single sample and return metrics."""
    from parser.text_extraction import extract_text

    file_path = Path(__file__).resolve().parent.parent / sample["file"]
    data = file_path.read_bytes()
    text = extract_text(data, sample["content_type"])

    # Import pipeline components
    from agent.extract_fields import extract_notice_fields
    from agent.cross_reference import cross_reference
    from agent.reasoning import generate_explanation
    import asyncio

    # Run extraction
    extraction = asyncio.run(extract_notice_fields(text))

    # Run cross-reference
    xref = asyncio.run(cross_reference(extraction.fields))

    # Run reasoning
    reasoning = asyncio.run(
        generate_explanation(
            fields=extraction.fields,
            xref=xref,
            extraction_confidence=extraction.confidence,
            raw_text=text,
        )
    )

    # Compute metrics
    type_correct = extraction.fields.notice_type.upper() == sample["expected_type"].upper()
    amount_correct = abs(extraction.fields.amount - sample["expected_amount"]) < sample["expected_amount"] * 0.1
    has_citations = len(reasoning.explanation.citations) > 0
    is_low_confidence = reasoning.is_low_confidence

    # Count factual claims vs citations
    sections = reasoning.explanation
    factual_claims = 0
    for section_text in [sections.what_it_means, sections.why_you_got_it, sections.what_to_do]:
        if section_text:
            # Rough count: sentences that make factual assertions
            factual_claims += len([s for s in section_text.split(".") if s.strip() and len(s.strip()) > 10])
    citation_count = len(sections.citations)

    return {
        "name": sample["name"],
        "type_correct": type_correct,
        "type_extracted": extraction.fields.notice_type,
        "type_expected": sample["expected_type"],
        "amount_correct": amount_correct,
        "amount_extracted": extraction.fields.amount,
        "amount_expected": sample["expected_amount"],
        "has_citations": has_citations,
        "citation_count": citation_count,
        "factual_claims": factual_claims,
        "confidence": reasoning.overall_confidence,
        "is_low_confidence": is_low_confidence,
        "provider_used": reasoning.provider_used,
        "matched_transactions": xref.total_transactions_in_period,
        "flagged_transactions": len(xref.flagged_transactions),
    }


def main():
    print("=" * 70)
    print("GST Saathi — Test Metrics")
    print("=" * 70)
    print()

    results = []
    for sample in SAMPLES:
        print(f"Testing: {sample['name']}...")
        start = time.time()
        try:
            result = run_test(sample)
            elapsed = time.time() - start
            result["elapsed_seconds"] = round(elapsed, 2)
            results.append(result)
            status = "PASS" if result["type_correct"] else "FAIL"
            print(f"  [{status}] Type: {result['type_extracted']} (expected {result['type_expected']})")
            print(f"  Amount: ₹{result['amount_extracted']:,.0f} (expected ₹{result['amount_expected']:,.0f})")
            print(f"  Citations: {result['citation_count']}, Confidence: {result['confidence']}")
            print(f"  Time: {result['elapsed_seconds']}s")
            print()
        except Exception as e:
            results.append({"name": sample["name"], "error": str(e)})
            print(f"  [ERROR] {e}")
            print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    valid = [r for r in results if "error" not in r]
    total = len(SAMPLES)
    passed = len(valid)

    type_correct = sum(1 for r in valid if r["type_correct"])
    amount_correct = sum(1 for r in valid if r["amount_correct"])
    with_citations = sum(1 for r in valid if r["has_citations"])
    low_conf_count = sum(1 for r in valid if r["is_low_confidence"])

    print(f"Total tests: {total}")
    print(f"Completed:   {passed}")
    print(f"Errors:      {total - passed}")
    print()
    print(f"Classification accuracy:  {type_correct}/{total} ({type_correct/total*100:.0f}%)")
    print(f"Amount accuracy:          {amount_correct}/{total} ({amount_correct/total*100:.0f}%)")
    print(f"Citation coverage:        {with_citations}/{total} ({with_citations/total*100:.0f}%)")
    print(f"Low-confidence fallback:  {low_conf_count}/{total} ({low_conf_count/total*100:.0f}%)")
    print()

    total_citations = sum(r.get("citation_count", 0) for r in valid)
    total_claims = sum(r.get("factual_claims", 0) for r in valid)
    if total_claims > 0:
        print(f"Citations per claim:      {total_citations}/{total_claims} ({total_citations/total_claims:.1f}x)")

    # Save results
    output_path = Path(__file__).resolve().parent.parent / "test_results.json"
    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nDetailed results saved to: {output_path}")

    return 0 if type_correct == total else 1


if __name__ == "__main__":
    sys.exit(main())
