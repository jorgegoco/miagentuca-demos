"""
Validation Logic - Execution Layer

Deterministic validation checks for loan application documents.
Checks name matching, document recency, and total assets.
"""

import re
from typing import Dict, List, Optional


# Fields that contain a person's name
NAME_FIELDS = {"account_owner", "employee_name", "name"}

# Fields that may contain a year
YEAR_FIELDS = {"w2_year", "investment_year", "issue_date", "end_date", "pay_period"}


def extract_year(value) -> Optional[int]:
    """
    Extract a 4-digit year (1900-2099) from a value.

    Args:
        value: String or number that may contain a year.

    Returns:
        Extracted year as int, or None if not found.
    """
    if value is None:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", str(value))
    return int(match.group(0)) if match else None


def check_name_match(documents: List[Dict]) -> Dict:
    """
    Verify all name fields across documents match.

    Args:
        documents: List of dicts with "extracted_data" containing field values.

    Returns:
        Dict with "passed" (bool), "names_found" (list of unique names),
        and "details" (per-document breakdown).
    """
    names_found = []
    details = []

    for doc in documents:
        extracted = doc.get("extracted_data", {})
        for field, value in extracted.items():
            if field in NAME_FIELDS and value:
                names_found.append(str(value).strip())
                details.append({
                    "filename": doc.get("filename", "unknown"),
                    "field": field,
                    "value": str(value).strip(),
                })

    unique_names = list(set(names_found))
    passed = len(unique_names) <= 1

    return {
        "passed": passed,
        "names_found": unique_names,
        "details": details,
    }


def check_years(documents: List[Dict]) -> Dict:
    """
    Extract and report the year associated with each document.

    Args:
        documents: List of dicts with "extracted_data" containing field values.

    Returns:
        Dict with "years_found" (list of per-document year info).
    """
    years_found = []

    for doc in documents:
        extracted = doc.get("extracted_data", {})
        for field, value in extracted.items():
            if field in YEAR_FIELDS:
                year = extract_year(value)
                if year is not None:
                    years_found.append({
                        "filename": doc.get("filename", "unknown"),
                        "field": field,
                        "raw_value": str(value),
                        "year": year,
                    })

    return {"years_found": years_found}


def calculate_total_assets(documents: List[Dict]) -> Dict:
    """
    Sum bank balances and investment values from extracted data.

    Args:
        documents: List of dicts with "document_type" and "extracted_data".

    Returns:
        Dict with bank_total, investment_total, and grand_total.
    """
    bank_total = 0.0
    investment_total = 0.0

    for doc in documents:
        doc_type = doc.get("document_type", "")
        extracted = doc.get("extracted_data", {})

        if doc_type == "bank_statement":
            balance = extracted.get("balance")
            if balance is not None:
                try:
                    bank_total += float(balance)
                except (ValueError, TypeError):
                    pass

        elif doc_type == "investment_statement":
            value = extracted.get("investment_value")
            if value is not None:
                try:
                    investment_total += float(value)
                except (ValueError, TypeError):
                    pass

    return {
        "bank_total": round(bank_total, 2),
        "investment_total": round(investment_total, 2),
        "grand_total": round(bank_total + investment_total, 2),
    }


def build_summary_table(documents: List[Dict]) -> List[Dict]:
    """
    Build a flat summary table of all extracted fields across documents.

    Args:
        documents: List of dicts with filename, document_type, and extracted_data.

    Returns:
        List of dicts, each with document_name, document_type, field, value.
    """
    rows = []

    for doc in documents:
        extracted = doc.get("extracted_data", {})
        for field, value in extracted.items():
            rows.append({
                "document_name": doc.get("filename", "unknown"),
                "document_type": doc.get("document_type", "unknown"),
                "field": field,
                "value": value,
            })

    return rows


def run_all_validations(documents: List[Dict]) -> Dict:
    """
    Run all validation checks on processed documents.

    Args:
        documents: List of processed document dicts.

    Returns:
        Dict with name_match, year_check, and total_assets results.
    """
    return {
        "name_match": check_name_match(documents),
        "year_check": check_years(documents),
        "total_assets": calculate_total_assets(documents),
    }


if __name__ == "__main__":
    # Quick test with sample data
    sample_docs = [
        {
            "filename": "uploadA.pdf",
            "document_type": "bank_statement",
            "extracted_data": {
                "account_owner": "John Doe",
                "balance": 25000.50,
                "end_date": "2024-12-31",
            },
        },
        {
            "filename": "uploadB.pdf",
            "document_type": "investment_statement",
            "extracted_data": {
                "account_owner": "John Doe",
                "investment_value": 50000.00,
                "investment_year": 2024,
            },
        },
    ]

    import json
    result = run_all_validations(sample_docs)
    print(json.dumps(result, indent=2))
    print("\nSummary table:")
    print(json.dumps(build_summary_table(sample_docs), indent=2))
