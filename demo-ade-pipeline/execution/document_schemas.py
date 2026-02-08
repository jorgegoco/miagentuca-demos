"""
Document Schemas - Execution Layer

Pydantic schemas for document categorization and type-specific field extraction.
Adapted from the Document AI course (L9 - Loan Application Pipeline).
"""

from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document types for loan applications."""
    ID = "ID"
    W2 = "W2"
    pay_stub = "pay_stub"
    bank_statement = "bank_statement"
    investment_statement = "investment_statement"


class DocType(BaseModel):
    """Schema for document type categorization."""
    type: DocumentType = Field(
        description="The type of document being analyzed.",
        title="Document Type",
    )


# ---------------------------------------------------------
# Schema for Government ID
# ---------------------------------------------------------
class IDSchema(BaseModel):
    name: str = Field(
        description="Full name of the person",
        title="Full Name"
    )
    issuer: str = Field(
        description="The state or country issuing the identification.",
        title="Issuer"
    )
    issue_date: str = Field(
        description="The issue date for the identification.",
        title="Issue Date"
    )
    identifier: str = Field(
        description="The unique identifier such as a drivers license number "
                    "or passport number",
        title="Identifier"
    )


# ---------------------------------------------------------
# Schema for W2
# ---------------------------------------------------------
class W2Schema(BaseModel):
    employee_name: str = Field(
        description="The name of the employee.",
        title="Employee Name"
    )
    employer_name: str = Field(
        description="The name of the employer organization issuing the W2.",
        title="Employer Name"
    )
    w2_year: int = Field(
        description="The year of the W2 form.",
        title="W2 Year"
    )
    wages_box_1: float = Field(
        description="The total wages shown in box 1 of the form",
        title="Box 1"
    )


# ---------------------------------------------------------
# Schema for Pay Stubs
# ---------------------------------------------------------
class PaymentStubSchema(BaseModel):
    employee_name: str = Field(
        description="The name of the employee.",
        title="Employee Name"
    )
    employer_name: str = Field(
        description="The name of the employer organization.",
        title="Employer Name"
    )
    pay_period: str = Field(
        description="The pay period for the stub.",
        title="Pay Period"
    )
    gross_pay: float = Field(
        description="The gross pay amount.",
        title="Gross Pay"
    )
    net_pay: float = Field(
        description="The net pay amount after deductions.",
        title="Net Pay"
    )


# ---------------------------------------------------------
# Schema for Bank Statements
# ---------------------------------------------------------
class BankStatementSchema(BaseModel):
    account_owner: str = Field(
        description="The name of the account owner(s).",
        title="Account Owner"
    )
    bank_name: str = Field(
        description="The name of the bank.",
        title="Bank Name"
    )
    account_number: str = Field(
        description="The bank account number.",
        title="Account Number"
    )
    end_date: str = Field(
        description="The ending date for the statement.",
        title="End Date"
    )
    balance: float = Field(
        description="The current balance of the bank account.",
        title="Bank Balance"
    )


# ---------------------------------------------------------
# Schema for Investment Statements
# ---------------------------------------------------------
class InvestmentStatementSchema(BaseModel):
    account_owner: str = Field(
        description="The name of the account owner(s).",
        title="Account Owner"
    )
    institution_name: str = Field(
        description="The name of the financial institution.",
        title="Institution Name"
    )
    investment_year: int = Field(
        description="The year of the investment statement.",
        title="Investment Year"
    )
    investment_value: float = Field(
        description="The total value of the account as of the statement "
                    "end date.",
        title="Investment Balance"
    )


# ---------------------------------------------------------
# Map document types to their corresponding schemas
# ---------------------------------------------------------
SCHEMA_PER_DOC_TYPE = {
    "bank_statement": BankStatementSchema,
    "investment_statement": InvestmentStatementSchema,
    "pay_stub": PaymentStubSchema,
    "ID": IDSchema,
    "W2": W2Schema,
}
