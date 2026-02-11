# Directive: Loan Application Document Pipeline

## Purpose

Process multiple loan application documents (uploaded with arbitrary filenames), automatically classify each document type, extract type-specific financial data using Pydantic schemas, and validate consistency across all documents.

## Input

- **Document files**: Up to 10 files. Supports PDFs, images, text documents, presentations, and spreadsheets (see docs.landing.ai/ade/ade-file-types). Max 5MB each.
- Documents arrive with arbitrary filenames (e.g., "uploadA.pdf", "image456.jpg")

## Process

### Step 1: Validate Input
- Check file count does not exceed MAX_FILES (10)
- Check each file extension against supported ADE file types (see docs.landing.ai/ade/ade-file-types)
- Check each file does not exceed MAX_FILE_SIZE_MB (5MB)
- Save all files to temporary directory

### Step 2: Parse and Categorize Each Document
- Tool: `execution/ade_client.py` -> `parse_document(split="page")`
- For each document:
  - Parse with ADE (model: `dpt-2-latest`, split by page)
  - Use first page markdown to determine document type
  - Tool: `execution/ade_client.py` -> `extract_fields()` with DocType schema
  - Classify into one of: ID, W2, pay_stub, bank_statement, investment_statement

### Step 3: Extract Type-Specific Fields
- Tool: `execution/document_schemas.py` -> `SCHEMA_PER_DOC_TYPE`
- For each classified document:
  - Look up the appropriate Pydantic schema (IDSchema, W2Schema, etc.)
  - Extract fields using full document markdown
  - Store extraction results and metadata

### Step 4: Validate Across Documents
- Tool: `execution/validation_logic.py` -> `run_all_validations()`
- **Name matching**: Verify all name fields across documents match
- **Year check**: Extract and report years from each document
- **Total assets**: Sum bank balances + investment values

### Step 5: Return Comprehensive Results
- Per-document: filename, type, extracted data, metadata
- Validation results: name match, year check, total assets
- Summary table: flat list of all extracted fields

## Document Types and Schemas

| Type | Schema | Key Fields |
|------|--------|------------|
| ID | IDSchema | name, issuer, issue_date, identifier |
| W2 | W2Schema | employee_name, employer_name, w2_year, wages_box_1 |
| pay_stub | PaymentStubSchema | employee_name, employer_name, pay_period, gross_pay, net_pay |
| bank_statement | BankStatementSchema | account_owner, bank_name, account_number, end_date, balance |
| investment_statement | InvestmentStatementSchema | account_owner, institution_name, investment_year, investment_value |

## Output

```json
{
  "success": true,
  "documents_processed": 5,
  "documents": [
    {
      "filename": "uploadA.pdf",
      "document_type": "investment_statement",
      "extracted_data": {"account_owner": "...", "investment_value": 50000},
      "metadata": {"account_owner": {"references": ["chunk_id"]}}
    }
  ],
  "validation": {
    "name_match": {"passed": true, "names_found": ["John Doe"]},
    "year_check": {"years_found": [{"filename": "...", "year": 2024}]},
    "total_assets": {"bank_total": 25000, "investment_total": 50000, "grand_total": 75000}
  },
  "summary_table": [
    {"document_name": "uploadA.pdf", "document_type": "investment_statement", "field": "account_owner", "value": "John Doe"}
  ]
}
```

## Edge Cases

- **Unrecognizable document**: If ADE cannot categorize, return with document_type "unknown" and skip extraction
- **Partial extraction failure**: Continue processing other documents; report per-document errors
- **Name mismatch**: Flag but don't reject (applicants may have different names on old documents)
- **Missing year fields**: Skip year check for documents without date-related fields
- **Zero assets**: Valid result (not all applicants have bank/investment statements)
- **Single document**: Pipeline works with 1 document (validation has less to compare)
- **ADE schema compatibility**: ADE Extract API does not support `allOf`, `$ref`, or `$defs` keywords. When using Pydantic models with Enum fields, `pydantic_to_json_schema()` may generate unsupported schemas. Use flat inline JSON schemas for categorization instead.

## Rate Limiting

- 3 requests per minute, 10 per day per IP (pipeline is heavier than single parse)
- Proxy-aware (extracts real IP from X-Forwarded-For behind Traefik)

## Security

- All uploaded files saved to temp directory, deleted after processing
- No file contents or extracted PII logged (only filenames, types, counts)
- API key stored in environment, never exposed in responses
