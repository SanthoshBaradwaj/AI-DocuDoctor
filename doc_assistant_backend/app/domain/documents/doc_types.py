from enum import Enum
from typing import Literal, Dict, List
from pydantic import BaseModel


class DocumentDomain(str, Enum):
    """Document domain categories."""
    IDENTITY = "IDENTITY"
    IMMIGRATION = "IMMIGRATION"
    INSURANCE = "INSURANCE"
    VEHICLES = "VEHICLES"
    FINANCE = "FINANCE"
    EMPLOYMENT_HR = "EMPLOYMENT_HR"


class DocumentType(str, Enum):
    """Specific document types across all domains."""
    # Identity & Government IDs
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    
    # Immigration & Travel
    VISA = "VISA"
    I94_OR_ENTRY_RECORD = "I94_OR_ENTRY_RECORD"
    I797_OR_STATUS_NOTICE = "I797_OR_STATUS_NOTICE"
    
    # Insurance (Health/Auto)
    HEALTH_INSURANCE_POLICY = "HEALTH_INSURANCE_POLICY"
    AUTO_INSURANCE_POLICY = "AUTO_INSURANCE_POLICY"
    INSURANCE_ID_CARD = "INSURANCE_ID_CARD"
    
    # Vehicles & Transportation
    VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
    
    # Finance & Banking
    BANK_STATEMENT = "BANK_STATEMENT"
    CREDIT_CARD_STATEMENT = "CREDIT_CARD_STATEMENT"
    LOAN_OR_MORTGAGE_AGREEMENT = "LOAN_OR_MORTGAGE_AGREEMENT"
    
    # Employment & HR
    PAYSLIP_OR_PAYSTUB = "PAYSLIP_OR_PAYSTUB"
    EMPLOYMENT_CONTRACT = "EMPLOYMENT_CONTRACT"
    BENEFITS_SUMMARY = "BENEFITS_SUMMARY"


class FieldConfig(BaseModel):
    """Configuration for a field in a document type."""
    name: str  # e.g. "passport_number"
    label: str  # human label to show in UI
    type: Literal["string", "date", "number", "bool"]
    required: bool = False
    drives_expiry: bool = False  # true if this field is used for reminders


class DocTypeConfig(BaseModel):
    """Configuration for a document type."""
    type: DocumentType
    domain: DocumentDomain
    display_name: str
    description: str
    fields: List[FieldConfig]


# Document Type Registry
DOC_TYPE_REGISTRY: Dict[DocumentType, DocTypeConfig] = {
    # Identity & Government IDs
    DocumentType.PASSPORT: DocTypeConfig(
        type=DocumentType.PASSPORT,
        domain=DocumentDomain.IDENTITY,
        display_name="Passport",
        description="International passport document",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="passport_number", label="Passport Number", type="string", required=True),
            FieldConfig(name="nationality", label="Nationality", type="string", required=False),
            FieldConfig(name="date_of_birth", label="Date of Birth", type="date", required=False),
            FieldConfig(name="date_of_issue", label="Date of Issue", type="date", required=False),
            FieldConfig(name="date_of_expiry", label="Date of Expiry", type="date", required=False, drives_expiry=True),
        ],
    ),
    DocumentType.NATIONAL_ID: DocTypeConfig(
        type=DocumentType.NATIONAL_ID,
        domain=DocumentDomain.IDENTITY,
        display_name="National ID",
        description="National or state ID card (Aadhaar, SSN card, etc.)",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="id_number", label="ID Number", type="string", required=True),
            FieldConfig(name="date_of_birth", label="Date of Birth", type="date", required=False),
            FieldConfig(name="date_of_issue", label="Date of Issue", type="date", required=False),
            FieldConfig(name="date_of_expiry", label="Date of Expiry", type="date", required=False, drives_expiry=True),
        ],
    ),
    DocumentType.DRIVERS_LICENSE: DocTypeConfig(
        type=DocumentType.DRIVERS_LICENSE,
        domain=DocumentDomain.IDENTITY,
        display_name="Driver's License",
        description="Driver's license or driving permit",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="license_number", label="License Number", type="string", required=True),
            FieldConfig(name="date_of_birth", label="Date of Birth", type="date", required=False),
            FieldConfig(name="date_of_issue", label="Date of Issue", type="date", required=False),
            FieldConfig(name="date_of_expiry", label="Date of Expiry", type="date", required=False, drives_expiry=True),
        ],
    ),
    
    # Immigration & Travel
    DocumentType.VISA: DocTypeConfig(
        type=DocumentType.VISA,
        domain=DocumentDomain.IMMIGRATION,
        display_name="Visa",
        description="Travel or immigration visa",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="country", label="Country", type="string", required=False),
            FieldConfig(name="visa_class", label="Visa Class", type="string", required=False),
            FieldConfig(name="visa_number", label="Visa Number", type="string", required=True),
            FieldConfig(name="valid_from", label="Valid From", type="date", required=False),
            FieldConfig(name="valid_to", label="Valid To", type="date", required=False, drives_expiry=True),
        ],
    ),
    DocumentType.I94_OR_ENTRY_RECORD: DocTypeConfig(
        type=DocumentType.I94_OR_ENTRY_RECORD,
        domain=DocumentDomain.IMMIGRATION,
        display_name="I-94 or Entry Record",
        description="I-94 arrival/departure record or entry document",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="admission_number", label="Admission Number", type="string", required=True),
            FieldConfig(name="date_of_entry", label="Date of Entry", type="date", required=False),
            FieldConfig(name="date_of_expiry", label="Date of Expiry", type="date", required=False, drives_expiry=True),
        ],
    ),
    DocumentType.I797_OR_STATUS_NOTICE: DocTypeConfig(
        type=DocumentType.I797_OR_STATUS_NOTICE,
        domain=DocumentDomain.IMMIGRATION,
        display_name="I-797 or Status Notice",
        description="I-797 approval notice or immigration status document",
        fields=[
            FieldConfig(name="full_name", label="Full Name", type="string", required=True),
            FieldConfig(name="receipt_number", label="Receipt Number", type="string", required=True),
            FieldConfig(name="notice_date", label="Notice Date", type="date", required=False),
            FieldConfig(name="valid_until", label="Valid Until", type="date", required=False, drives_expiry=True),
        ],
    ),
    
    # Insurance
    DocumentType.HEALTH_INSURANCE_POLICY: DocTypeConfig(
        type=DocumentType.HEALTH_INSURANCE_POLICY,
        domain=DocumentDomain.INSURANCE,
        display_name="Health Insurance Policy",
        description="Health insurance policy document",
        fields=[
            FieldConfig(name="policy_holder_name", label="Policy Holder Name", type="string", required=True),
            FieldConfig(name="policy_number", label="Policy Number", type="string", required=True),
            FieldConfig(name="insurer_name", label="Insurer Name", type="string", required=False),
            FieldConfig(name="effective_date", label="Effective Date", type="date", required=False),
            FieldConfig(name="expiry_date", label="Expiry Date", type="date", required=False, drives_expiry=True),
            FieldConfig(name="coverage_type", label="Coverage Type", type="string", required=False),
        ],
    ),
    DocumentType.AUTO_INSURANCE_POLICY: DocTypeConfig(
        type=DocumentType.AUTO_INSURANCE_POLICY,
        domain=DocumentDomain.INSURANCE,
        display_name="Auto Insurance Policy",
        description="Automobile insurance policy document",
        fields=[
            FieldConfig(name="policy_holder_name", label="Policy Holder Name", type="string", required=True),
            FieldConfig(name="policy_number", label="Policy Number", type="string", required=True),
            FieldConfig(name="insurer_name", label="Insurer Name", type="string", required=False),
            FieldConfig(name="vehicle_id", label="Vehicle ID", type="string", required=False),
            FieldConfig(name="effective_date", label="Effective Date", type="date", required=False),
            FieldConfig(name="expiry_date", label="Expiry Date", type="date", required=False, drives_expiry=True),
            FieldConfig(name="coverage_type", label="Coverage Type", type="string", required=False),
            FieldConfig(name="deductible", label="Deductible", type="number", required=False),
        ],
    ),
    DocumentType.INSURANCE_ID_CARD: DocTypeConfig(
        type=DocumentType.INSURANCE_ID_CARD,
        domain=DocumentDomain.INSURANCE,
        display_name="Insurance ID Card",
        description="Insurance identification card",
        fields=[
            FieldConfig(name="member_name", label="Member Name", type="string", required=True),
            FieldConfig(name="member_id", label="Member ID", type="string", required=True),
            FieldConfig(name="group_number", label="Group Number", type="string", required=False),
            FieldConfig(name="insurer_name", label="Insurer Name", type="string", required=False),
        ],
    ),
    
    # Vehicles & Transportation
    DocumentType.VEHICLE_REGISTRATION: DocTypeConfig(
        type=DocumentType.VEHICLE_REGISTRATION,
        domain=DocumentDomain.VEHICLES,
        display_name="Vehicle Registration",
        description="Vehicle registration document",
        fields=[
            FieldConfig(name="owner_name", label="Owner Name", type="string", required=True),
            FieldConfig(name="registration_number", label="Registration Number", type="string", required=True),
            FieldConfig(name="vehicle_id", label="Vehicle ID (VIN)", type="string", required=False),
            FieldConfig(name="state_or_region", label="State/Region", type="string", required=False),
            FieldConfig(name="date_of_issue", label="Date of Issue", type="date", required=False),
            FieldConfig(name="expiry_date", label="Expiry Date", type="date", required=False, drives_expiry=True),
        ],
    ),
    
    # Finance & Banking
    DocumentType.BANK_STATEMENT: DocTypeConfig(
        type=DocumentType.BANK_STATEMENT,
        domain=DocumentDomain.FINANCE,
        display_name="Bank Statement",
        description="Bank account statement",
        fields=[
            FieldConfig(name="account_holder", label="Account Holder", type="string", required=True),
            FieldConfig(name="account_number", label="Account Number", type="string", required=False),
            FieldConfig(name="bank_name", label="Bank Name", type="string", required=False),
            FieldConfig(name="statement_period_start", label="Statement Period Start", type="date", required=False),
            FieldConfig(name="statement_period_end", label="Statement Period End", type="date", required=False),
        ],
    ),
    DocumentType.CREDIT_CARD_STATEMENT: DocTypeConfig(
        type=DocumentType.CREDIT_CARD_STATEMENT,
        domain=DocumentDomain.FINANCE,
        display_name="Credit Card Statement",
        description="Credit card statement",
        fields=[
            FieldConfig(name="cardholder_name", label="Cardholder Name", type="string", required=True),
            FieldConfig(name="card_number", label="Card Number (last 4)", type="string", required=False),
            FieldConfig(name="statement_period_start", label="Statement Period Start", type="date", required=False),
            FieldConfig(name="statement_period_end", label="Statement Period End", type="date", required=False),
            FieldConfig(name="payment_due_date", label="Payment Due Date", type="date", required=False, drives_expiry=True),
        ],
    ),
    DocumentType.LOAN_OR_MORTGAGE_AGREEMENT: DocTypeConfig(
        type=DocumentType.LOAN_OR_MORTGAGE_AGREEMENT,
        domain=DocumentDomain.FINANCE,
        display_name="Loan or Mortgage Agreement",
        description="Loan or mortgage agreement document",
        fields=[
            FieldConfig(name="borrower_name", label="Borrower Name", type="string", required=True),
            FieldConfig(name="lender_name", label="Lender Name", type="string", required=False),
            FieldConfig(name="loan_number", label="Loan Number", type="string", required=False),
            FieldConfig(name="loan_amount", label="Loan Amount", type="number", required=False),
            FieldConfig(name="interest_rate", label="Interest Rate", type="number", required=False),
            FieldConfig(name="maturity_date", label="Maturity Date", type="date", required=False, drives_expiry=True),
        ],
    ),
    
    # Employment & HR
    DocumentType.PAYSLIP_OR_PAYSTUB: DocTypeConfig(
        type=DocumentType.PAYSLIP_OR_PAYSTUB,
        domain=DocumentDomain.EMPLOYMENT_HR,
        display_name="Payslip or Paystub",
        description="Employee payslip or paystub",
        fields=[
            FieldConfig(name="employee_name", label="Employee Name", type="string", required=True),
            FieldConfig(name="employer_name", label="Employer Name", type="string", required=False),
            FieldConfig(name="pay_period_start", label="Pay Period Start", type="date", required=False),
            FieldConfig(name="pay_period_end", label="Pay Period End", type="date", required=False),
            FieldConfig(name="gross_pay", label="Gross Pay", type="number", required=False),
            FieldConfig(name="net_pay", label="Net Pay", type="number", required=False),
        ],
    ),
    DocumentType.EMPLOYMENT_CONTRACT: DocTypeConfig(
        type=DocumentType.EMPLOYMENT_CONTRACT,
        domain=DocumentDomain.EMPLOYMENT_HR,
        display_name="Employment Contract",
        description="Employment contract or offer letter",
        fields=[
            FieldConfig(name="employee_name", label="Employee Name", type="string", required=True),
            FieldConfig(name="employer_name", label="Employer Name", type="string", required=False),
            FieldConfig(name="position", label="Position/Title", type="string", required=False),
            FieldConfig(name="start_date", label="Start Date", type="date", required=False),
            FieldConfig(name="end_date", label="End Date", type="date", required=False, drives_expiry=True),
            FieldConfig(name="salary", label="Salary", type="number", required=False),
        ],
    ),
    DocumentType.BENEFITS_SUMMARY: DocTypeConfig(
        type=DocumentType.BENEFITS_SUMMARY,
        domain=DocumentDomain.EMPLOYMENT_HR,
        display_name="Benefits Summary",
        description="Employee benefits summary document",
        fields=[
            FieldConfig(name="employee_name", label="Employee Name", type="string", required=True),
            FieldConfig(name="employer_name", label="Employer Name", type="string", required=False),
            FieldConfig(name="benefit_types", label="Benefit Types", type="string", required=False),
            FieldConfig(name="effective_date", label="Effective Date", type="date", required=False),
            FieldConfig(name="expiry_date", label="Expiry Date", type="date", required=False, drives_expiry=True),
        ],
    ),
}


# Helper functions
def get_doc_type_config(doc_type: DocumentType) -> DocTypeConfig:
    """Get the configuration for a document type."""
    return DOC_TYPE_REGISTRY.get(doc_type)


def get_domain_for_doc_type(doc_type: DocumentType) -> DocumentDomain:
    """Get the domain for a document type."""
    config = get_doc_type_config(doc_type)
    if config:
        return config.domain
    raise ValueError(f"Unknown document type: {doc_type}")


def get_all_doc_types_for_domain(domain: DocumentDomain) -> List[DocumentType]:
    """Get all document types for a given domain."""
    return [
        doc_type
        for doc_type, config in DOC_TYPE_REGISTRY.items()
        if config.domain == domain
    ]

