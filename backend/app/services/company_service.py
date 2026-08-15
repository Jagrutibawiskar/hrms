from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.models.company import Company
from app.models.enums import (
    CalculationType,
    ComponentType,
    OnboardingStep,
    RoleName,
)
from app.models.organization import Location
from app.models.payroll import SalaryComponent, SalaryStructure, SalaryStructureComponent
from app.models.policy import LeaveType, WorkPolicy
from app.models.user import User
from app.services import auth_service
from app.utils.dates import utcnow

DEFAULT_LEAVE_TYPES = [
    {"name": "Casual Leave", "code": "CL", "annual_quota": 12, "is_paid": True},
    {"name": "Sick Leave", "code": "SL", "annual_quota": 6, "is_paid": True},
    {
        "name": "Earned Leave",
        "code": "EL",
        "annual_quota": 15,
        "is_paid": True,
        "carry_forward": True,
        "max_carry_forward": 30,
    },
    {
        "name": "Unpaid Leave",
        "code": "LWP",
        "annual_quota": 0,
        "is_paid": False,
        "requires_approval": True,
    },
]

DEFAULT_SALARY_COMPONENTS = [
    ("Basic", "BASIC", ComponentType.EARNING, CalculationType.PERCENT_OF_CTC, 50, 1, True),
    ("House Rent Allowance", "HRA", ComponentType.EARNING, CalculationType.PERCENT_OF_BASIC, 40, 2, True),
    ("Special Allowance", "SPECIAL", ComponentType.EARNING, CalculationType.PERCENT_OF_CTC, 20, 3, True),
    ("Conveyance Allowance", "CONVEY", ComponentType.EARNING, CalculationType.FIXED, 1600, 4, True),
    ("Bonus", "BONUS", ComponentType.EARNING, CalculationType.FIXED, 0, 5, True),
    ("Provident Fund", "PF", ComponentType.DEDUCTION, CalculationType.PERCENT_OF_BASIC, 12, 10, True),
    ("Employee State Insurance", "ESI", ComponentType.DEDUCTION, CalculationType.PERCENT_OF_GROSS, 0.75, 11, True),
    ("Professional Tax", "PT", ComponentType.DEDUCTION, CalculationType.FIXED, 200, 12, False),
    ("TDS", "TDS", ComponentType.DEDUCTION, CalculationType.FIXED, 0, 13, False),
]


def create_company(db: Session, user: User, payload) -> Company:
    if user.company_id is not None:
        raise Conflict("This account already belongs to a company")

    company = Company(
        name=payload.name.strip(),
        industry=payload.industry,
        company_size=payload.company_size.value,
        company_type=payload.company_type,
        email=str(payload.email).lower(),
        phone=payload.phone,
        website=payload.website,
        country=payload.country,
        state=payload.state,
        city=payload.city,
        address=payload.address,
        postal_code=payload.postal_code,
        timezone=payload.timezone,
        currency=payload.currency,
        fiscal_year_start_month=payload.fiscal_year_start_month,
        onboarding_step=OnboardingStep.ORGANIZATION,
        created_by_user_id=user.id,
    )
    db.add(company)
    db.flush()

    user.company_id = company.id
    auth_service.assign_role(db, user, RoleName.COMPANY_ADMIN, company.id)

    seed_company_defaults(db, company)
    db.flush()
    db.refresh(company)
    return company


def seed_company_defaults(db: Session, company: Company) -> None:
    """Sensible starting point so a new tenant is usable before the wizard finishes."""
    db.add(
        Location(
            company_id=company.id,
            name="Head Office",
            address=company.address,
            city=company.city,
            state=company.state,
            country=company.country,
            postal_code=company.postal_code,
            timezone=company.timezone,
            is_headquarters=True,
        )
    )
    db.add(
        WorkPolicy(
            company_id=company.id,
            name="Default Work Policy",
            working_days=[1, 2, 3, 4, 5],
            start_time=time(9, 30),
            end_time=time(18, 30),
            break_start=time(13, 0),
            break_end=time(14, 0),
            full_day_hours=8,
            half_day_hours=4,
            late_grace_minutes=15,
            is_default=True,
        )
    )
    for spec in DEFAULT_LEAVE_TYPES:
        db.add(LeaveType(company_id=company.id, **spec))

    components: list[SalaryComponent] = []
    for name, code, ctype, calc, value, order, prorate in DEFAULT_SALARY_COMPONENTS:
        component = SalaryComponent(
            company_id=company.id,
            name=name,
            code=code,
            component_type=ctype,
            calculation_type=calc,
            default_value=value,
            display_order=order,
            prorate_on_lop=prorate,
        )
        db.add(component)
        components.append(component)
    db.flush()

    structure = SalaryStructure(
        company_id=company.id,
        name="Standard",
        description="Default CTC breakup: Basic 50%, HRA 40% of Basic, Special 20% of CTC.",
    )
    db.add(structure)
    db.flush()
    for component in components:
        db.add(
            SalaryStructureComponent(
                structure_id=structure.id,
                component_id=component.id,
                value=float(component.default_value),
            )
        )
    db.flush()


def advance_step(db: Session, company: Company, completed: OnboardingStep) -> Company:
    """Moves the wizard forward, never backwards (re-editing a step is allowed)."""
    order = list(OnboardingStep)
    try:
        next_step = order[order.index(completed) + 1]
    except (ValueError, IndexError):
        next_step = OnboardingStep.COMPLETED

    if order.index(next_step) > order.index(company.onboarding_step):
        company.onboarding_step = next_step

    if next_step == OnboardingStep.COMPLETED:
        complete_onboarding(db, company)
    return company


def complete_onboarding(db: Session, company: Company) -> Company:
    company.onboarding_step = OnboardingStep.COMPLETED
    if not company.is_onboarded:
        company.is_onboarded = True
        company.onboarded_at = utcnow()
    return company


def get_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFound("Company not found")
    return company


def require_default_work_policy(db: Session, company_id: int) -> WorkPolicy:
    policy = db.scalar(
        select(WorkPolicy).where(
            WorkPolicy.company_id == company_id, WorkPolicy.is_active.is_(True)
        )
    )
    if policy is None:
        raise BadRequest("No work policy is configured for this company")
    return policy
