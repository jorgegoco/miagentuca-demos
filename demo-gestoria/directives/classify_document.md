# Directive: Classify and Extract Information from Documents

## Goal
Classify uploaded PDF documents into specific types and extract relevant information based on the document type. This is designed for Spanish gestorías (accounting firms) handling client documents.

## Input
- PDF file (max 2MB)
- Uploaded via API endpoint

## Document Types to Recognize

### 1. Factura (Invoice)
**Identification signals:**
- Contains words: "factura", "invoice", "importe", "IVA", "total"
- Has structured pricing information
- Includes company tax ID (CIF/NIF)

**Information to extract:**
- Invoice number
- Date (fecha)
- Issuing company name
- Total amount (importe total)
- Tax amount (IVA)
- Recipient company

### 2. Albarán (Delivery Note)
**Identification signals:**
- Contains words: "albarán", "delivery note", "entrega"
- Lists items/products but often no prices
- May have signature field

**Information to extract:**
- Delivery note number
- Date
- Supplier name
- Items delivered (list)
- Recipient

### 3. Presupuesto (Quote/Estimate)
**Identification signals:**
- Contains words: "presupuesto", "quotation", "estimate", "válido hasta"
- Future-dated validity period
- Conditional language ("sujeto a", "según disponibilidad")

**Information to extract:**
- Quote number
- Date
- Validity period (valid until)
- Company providing quote
- Total estimated amount
- Items/services quoted

### 4. Contrato (Contract)
**Identification signals:**
- Contains words: "contrato", "agreement", "partes", "cláusulas"
- Legal language
- Multiple sections/clauses
- Signature fields for multiple parties

**Information to extract:**
- Contract type (e.g., service contract, employment)
- Parties involved (names)
- Start date
- Duration/end date if specified
- Key terms (brief summary)

### 5. Nómina (Payroll/Pay Slip)
**Identification signals:**
- Contains words: "nómina", "payroll", "salario", "cotización"
- Employee personal data
- Detailed salary breakdown
- Social security numbers

**Information to extract:**
- Employee name
- Period (month/year)
- Gross salary (salario bruto)
- Net salary (salario neto)
- Company name

### 6. Recibo (Receipt)
**Identification signals:**
- Contains words: "recibo", "receipt", "pagado"
- Simple transaction record
- Often handwritten or simple format

**Information to extract:**
- Date
- Amount paid
- Concept/description
- Payee name

### 7. Certificado (Certificate)
**Identification signals:**
- Contains words: "certificado", "certifica que", "certificate"
- Formal letterhead
- Signature and stamp
- Official tone

**Information to extract:**
- Certificate type
- Issued to (person/company)
- Issuing authority
- Date
- Purpose/subject

### 8. Otro (Other/Unknown)
**When to use:**
- Document doesn't match any of the above patterns
- Multiple document types in one file
- Unclear or damaged document

**Information to extract:**
- Brief description of what the document appears to be
- Any identifiable dates, names, or amounts

## Tools to Use

### Step 1: Extract Text
Use `execution/pdf_parser.py` to extract text from the uploaded PDF.

**Input:** PDF file path
**Output:** Extracted text string

### Step 2: Classify and Extract
Send extracted text to Claude API with classification instructions.

**Prompt structure:**
```
You are analyzing a document from a Spanish accounting firm (gestoría).

Document text:
[EXTRACTED_TEXT]

Task:
1. Classify the document type: factura, albarán, presupuesto, contrato, nómina, recibo, certificado, or otro
2. Extract relevant information based on the document type (see extraction rules above)
3. Provide confidence score (0-100)

Return JSON format:
{
  "document_type": "factura|albarán|presupuesto|contrato|nómina|recibo|certificado|otro",
  "confidence": 85,
  "extracted_data": {
    // Type-specific fields
  },
  "notes": "Any relevant observations or warnings"
}
```

## Output Format

Return JSON response to the API client:

```json
{
  "success": true,
  "document_type": "factura",
  "confidence": 92,
  "extracted_data": {
    "invoice_number": "FAC-2024-001",
    "date": "2024-01-15",
    "company": "Suministros García SL",
    "total_amount": "1,234.56",
    "tax_amount": "259.26",
    "recipient": "Construcciones López SA"
  },
  "notes": "High confidence classification. All key fields extracted."
}
```

## Edge Cases and Error Handling

### 1. File Too Large
- Max size: 2MB
- Return error: "File exceeds maximum size of 2MB"

### 2. Invalid PDF
- Cannot be parsed
- Return error: "Unable to read PDF file. File may be corrupted or password-protected."

### 3. Empty or Scanned Image PDF
- No extractable text
- Consider: May need OCR (future enhancement)
- Return: Low confidence classification with note "Document appears to be scanned image. Text extraction limited."

### 4. Multi-page Documents
- Process all pages
- Concatenate text for classification
- Note: If document type changes between pages, classify as "otro" with explanation

### 5. Low Confidence (<60%)
- Still return best guess
- Add warning in notes: "Low confidence classification. Manual review recommended."

### 6. Multiple Languages
- Primarily Spanish, but English invoices may appear
- Classify based on content structure, not just keywords

## Rate Limiting
- 5 requests per minute per IP address
- Return 429 error if exceeded: "Rate limit exceeded. Please try again in X seconds."

## Security Considerations
- Delete uploaded files from `.tmp/` after processing (max 1 hour retention)
- Do not log document contents
- Sanitize file names to prevent path traversal
- Validate file is actually PDF (magic bytes check)

## Success Criteria
- Classification accuracy >85% for clear documents
- Response time <5 seconds for documents under 10 pages
- Graceful error handling for all edge cases
- No leaked sensitive information in logs or errors

## Future Enhancements
- OCR support for scanned documents
- Multi-document PDFs (split and classify each)
- Batch upload capability
- Export to accounting software formats
- Historical tracking of document types per client
