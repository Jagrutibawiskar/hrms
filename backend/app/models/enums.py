import enum

from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls, **kwargs):
    """Portable string-backed enum column (VARCHAR on both SQLite and Postgres)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=40,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        **kwargs,
    )


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    HR = "HR"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class CompanySize(str, enum.Enum):
    S1_10 = "1-10"
    S11_50 = "11-50"
    S51_200 = "51-200"
    S201_500 = "201-500"
    S501_1000 = "501-1000"
    S1000_PLUS = "1000+"


class OnboardingStep(str, enum.Enum):
    COMPANY = "company"
    ORGANIZATION = "organization"
    WORK_POLICY = "work_policy"
    LEAVE_POLICY = "leave_policy"
    ADMIN = "admin"
    EMPLOYEES = "employees"
    COMPLETED = "completed"


ONBOARDING_ORDER = [
    OnboardingStep.COMPANY,
    OnboardingStep.ORGANIZATION,
    OnboardingStep.WORK_POLICY,
    OnboardingStep.LEAVE_POLICY,
    OnboardingStep.ADMIN,
    OnboardingStep.EMPLOYEES,
    OnboardingStep.COMPLETED,
]


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNDISCLOSED = "UNDISCLOSED"


class MaritalStatus(str, enum.Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    OTHER = "OTHER"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"
    CONSULTANT = "CONSULTANT"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PROBATION = "PROBATION"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    INACTIVE = "INACTIVE"
    TERMINATED = "TERMINATED"
    RESIGNED = "RESIGNED"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LATE = "LATE"
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"
    WFH = "WFH"
    WEEKEND = "WEEKEND"


class AttendanceLogType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class HalfDaySession(str, enum.Enum):
    FIRST_HALF = "FIRST_HALF"
    SECOND_HALF = "SECOND_HALF"


class HolidayType(str, enum.Enum):
    PUBLIC = "PUBLIC"
    OPTIONAL = "OPTIONAL"
    RESTRICTED = "RESTRICTED"
    COMPANY = "COMPANY"


class DocumentType(str, enum.Enum):
    RESUME = "RESUME"
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    OFFER_LETTER = "OFFER_LETTER"
    JOINING_LETTER = "JOINING_LETTER"
    EXPERIENCE_LETTER = "EXPERIENCE_LETTER"
    EDUCATION = "EDUCATION"
    ADDRESS_PROOF = "ADDRESS_PROOF"
    BANK_PROOF = "BANK_PROOF"
    WORK_PERMIT = "WORK_PERMIT"
    # Filed automatically when someone attaches proof to a leave request.
    LEAVE_ATTACHMENT = "LEAVE_ATTACHMENT"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    """Verification state of an uploaded document."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class WorkMode(str, enum.Enum):
    OFFICE = "OFFICE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"


class ProfileStatus(str, enum.Enum):
    """HR often creates a record before every document has arrived."""

    DRAFT = "DRAFT"
    COMPLETE = "COMPLETE"


class ComponentType(str, enum.Enum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class CalculationType(str, enum.Enum):
    FIXED = "FIXED"
    PERCENT_OF_BASIC = "PERCENT_OF_BASIC"
    PERCENT_OF_CTC = "PERCENT_OF_CTC"
    PERCENT_OF_GROSS = "PERCENT_OF_GROSS"


class PayrollStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class NotificationEvent(str, enum.Enum):
    LEAVE_APPLIED = "LEAVE_APPLIED"
    LEAVE_APPROVED = "LEAVE_APPROVED"
    LEAVE_REJECTED = "LEAVE_REJECTED"
    LEAVE_CANCELLED = "LEAVE_CANCELLED"
    PAYROLL_PROCESSED = "PAYROLL_PROCESSED"
    PAYSLIP_GENERATED = "PAYSLIP_GENERATED"
    EMPLOYEE_ADDED = "EMPLOYEE_ADDED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    ATTENDANCE_REGULARIZED = "ATTENDANCE_REGULARIZED"
