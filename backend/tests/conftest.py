import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway SQLite file before any app module is imported.
_tmp = Path(tempfile.mkdtemp(prefix="hrms_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.seed import seed_roles_and_permissions  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_roles_and_permissions(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


class ApiUser:
    """Thin wrapper that keeps the bearer token attached to every request."""

    def __init__(self, client: TestClient, token: str, extra_headers: dict | None = None):
        self.client = client
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", **(extra_headers or {})}

    def viewing(self, company_id: int) -> "ApiUser":
        """Same session, scoped to a company — the header the frontend sends."""
        return ApiUser(self.client, self.token, {"X-Company-Id": str(company_id)})

    def get(self, url, **kw):
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self.headers, **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self.headers, **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers=self.headers, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self.headers, **kw)


PASSWORD = "Password123!"


def signup(client, email: str, password: str = "Password123!", **extra) -> ApiUser:
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "first_name": "Test", **extra},
    )
    assert response.status_code == 201, response.text
    return ApiUser(client, response.json()["tokens"]["access_token"])


def login(client, email: str, password: str = "Password123!") -> ApiUser:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return ApiUser(client, response.json()["tokens"]["access_token"])


API = "/api/v1"


def build_company(client, slug: str, *, company_name: str) -> dict:
    """Creates a fully onboarded tenant with an admin, a manager and two staff.

    Each test module builds its own so the modules never fight over shared state.
    `slug` namespaces the email addresses.
    """
    admin = signup(client, f"admin@{slug}.co", first_name="Ada", last_name="Admin")

    response = admin.post(
        f"{API}/companies",
        json={
            "name": company_name,
            "industry": "Software",
            "company_size": "11-50",
            "email": f"hello@{slug}.co",
            "phone": "9876543210",
            "country": "India",
            "state": "Karnataka",
            "city": "Bengaluru",
            "address": "1 MG Road",
            "postal_code": "560001",
        },
    )
    assert response.status_code == 201, response.text
    company_id = response.json()["id"]

    # The signup token predates the company, so it still says company_id: null.
    admin = login(client, f"admin@{slug}.co")

    admin.post(
        f"{API}/onboarding/organization",
        json={
            "departments": [{"name": "Engineering"}, {"name": "People Ops"}],
            "designations": [{"name": "Software Engineer"}, {"name": "HR Manager"}],
            "locations": [{"name": "Head Office", "city": "Bengaluru"}],
        },
    )
    admin.post(
        f"{API}/onboarding/work-policy",
        json={
            "working_days": [1, 2, 3, 4, 5],
            "start_time": "09:30:00",
            "end_time": "18:30:00",
            "break_start": "13:00:00",
            "break_end": "14:00:00",
        },
    )
    admin.post(f"{API}/onboarding/leave-policy", json={"leave_types": []})
    admin.post(
        f"{API}/onboarding/admin",
        json={"first_name": "Ada", "last_name": "Admin", "phone": "9000000000"},
    )

    departments = {d["name"]: d["id"] for d in admin.get(f"{API}/organization/departments").json()}
    designations = {d["name"]: d["id"] for d in admin.get(f"{API}/organization/designations").json()}
    locations = {loc["name"]: loc["id"] for loc in admin.get(f"{API}/organization/locations").json()}

    def add(first, last, email_local, role, dept, desig, manager_id=None, is_manager=False):
        response = admin.post(
            f"{API}/employees",
            json={
                "first_name": first,
                "last_name": last,
                "work_email": f"{email_local}@{slug}.co",
                "password": PASSWORD,
                "role": role,
                "employment": {
                    "department_id": departments[dept],
                    "designation_id": designations[desig],
                    "location_id": locations["Head Office"],
                    "manager_id": manager_id,
                    "joining_date": "2024-01-15",
                    "is_manager": is_manager,
                },
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["employee"]["id"]

    manager_id = add("Maya", "Manager", "maya", "MANAGER", "Engineering", "Software Engineer", is_manager=True)
    employee_id = add("Eli", "Engineer", "eli", "EMPLOYEE", "Engineering", "Software Engineer", manager_id)
    add("Hana", "HR", "hana", "HR", "People Ops", "HR Manager")

    admin.post(f"{API}/onboarding/skip-employees")

    return {
        "slug": slug,
        "company_id": company_id,
        "admin": admin,
        "manager_id": manager_id,
        "employee_id": employee_id,
        "departments": departments,
        "designations": designations,
        "locations": locations,
    }
