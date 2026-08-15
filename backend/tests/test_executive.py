"""Executive (platform-level) access.

An executive can look into any company. Critically, nobody else can — a normal
company admin sending the same header must stay locked to their own tenant.
"""

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User
from app.models.enums import RoleName
from app.services import auth_service
from tests.conftest import API, ApiUser, build_company, login

EXEC_EMAIL = "exec@platform.co"
EXEC_PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def two_companies(client):
    """Two separate tenants, so cross-company access is actually meaningful."""
    first = build_company(client, "alpha", company_name="Alpha Industries")
    second = build_company(client, "beta", company_name="Beta Works")
    return first, second


@pytest.fixture(scope="module")
def executive(client, two_companies):
    """Created the way the real script does it: no company, SUPER_ADMIN role."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EXEC_EMAIL))
        if user is None:
            user = User(
                email=EXEC_EMAIL,
                password_hash=hash_password(EXEC_PASSWORD),
                first_name="Sovik",
                last_name="Executive",
                company_id=None,
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
            db.flush()
        auth_service.assign_role(db, user, RoleName.SUPER_ADMIN)
        db.commit()

    response = client.post(
        f"{API}/auth/login", json={"email": EXEC_EMAIL, "password": EXEC_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return ApiUser(client, response.json()["tokens"]["access_token"])


def viewing(user: ApiUser, company_id: int) -> ApiUser:
    """Same session, scoped to a company via the header the frontend sends."""
    return user.viewing(company_id)


def test_executive_is_flagged_and_belongs_to_no_company(executive):
    me = executive.get(f"{API}/auth/me").json()
    assert me["is_executive"] is True
    assert me["company_id"] is None
    assert "SUPER_ADMIN" in me["roles"]
    # Never held at the onboarding gate.
    assert me["is_onboarded"] is True


def test_executive_lists_every_company(executive, two_companies):
    companies = executive.get(f"{API}/companies").json()
    names = {c["name"] for c in companies}
    assert {"Alpha Industries", "Beta Works"} <= names


def test_executive_sees_each_company_in_turn(executive, two_companies):
    alpha, beta = two_companies

    alpha_view = viewing(executive, alpha["company_id"])
    people = alpha_view.get(f"{API}/employees?page_size=50").json()
    emails = {row["work_email"] for row in people["items"]}
    assert any(e.endswith("@alpha.co") for e in emails)
    assert not any(e.endswith("@beta.co") for e in emails)

    beta_view = viewing(executive, beta["company_id"])
    people = beta_view.get(f"{API}/employees?page_size=50").json()
    emails = {row["work_email"] for row in people["items"]}
    assert any(e.endswith("@beta.co") for e in emails)
    assert not any(e.endswith("@alpha.co") for e in emails)


def test_executive_me_reflects_the_company_being_viewed(executive, two_companies):
    alpha, beta = two_companies
    assert viewing(executive, alpha["company_id"]).get(f"{API}/auth/me").json()["company_name"] == "Alpha Industries"
    assert viewing(executive, beta["company_id"]).get(f"{API}/auth/me").json()["company_name"] == "Beta Works"


def test_executive_reaches_every_module_of_a_chosen_company(executive, two_companies):
    alpha, _ = two_companies
    view = viewing(executive, alpha["company_id"])
    for path in [
        "/companies/current",
        "/dashboard/hr",
        "/employees",
        "/attendance",
        "/leaves/requests",
        "/holidays",
        "/payroll/runs",
        "/reports/employees",
        "/compliance",
        "/organization/departments",
    ]:
        response = view.get(f"{API}{path}")
        assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:120]}"


def test_executive_without_a_company_is_told_to_pick_one(executive):
    response = executive.get(f"{API}/employees")
    assert response.status_code == 403
    assert "Select a company" in response.json()["detail"]


# ---------------------------------------------------------------- the security half


def test_company_admin_cannot_cross_tenants_with_the_header(two_companies, client):
    """The header is honoured only for executives — this is the whole safety story."""
    alpha, beta = two_companies
    alpha_admin = login(client, "admin@alpha.co")
    spoofed = alpha_admin.viewing(beta["company_id"])

    people = spoofed.get(f"{API}/employees?page_size=50").json()
    emails = {row["work_email"] for row in people["items"]}
    assert emails, "admin should still see their own company"
    assert all(e.endswith("@alpha.co") for e in emails), "header must not move a normal admin"

    company = spoofed.get(f"{API}/companies/current").json()
    assert company["name"] == "Alpha Industries"


def test_employee_cannot_list_companies(two_companies, client):
    employee = login(client, "eli@alpha.co")
    response = employee.get(f"{API}/companies")
    assert response.status_code == 403


def test_executive_rejects_an_unknown_company(executive):
    assert executive.viewing(999999).get(f"{API}/employees").status_code == 404
