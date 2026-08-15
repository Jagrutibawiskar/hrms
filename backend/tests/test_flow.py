"""End-to-end walk through the MVP-1 product flow.

signup -> create company -> onboarding wizard -> employees -> attendance ->
leave -> payroll -> payslips, plus multi-tenant isolation and RBAC checks.
"""

from datetime import date, timedelta

import pytest

from tests.conftest import login, signup

API = "/api/v1"


@pytest.fixture(scope="module")
def acme(client):
    """Company A, fully onboarded, with an HR user and two employees."""
    admin = signup(client, "admin@acme.co")

    response = admin.post(
        f"{API}/companies",
        json={
            "name": "Acme Corp",
            "industry": "Software",
            "company_size": "11-50",
            "company_type": "Private Limited",
            "email": "hello@acme.co",
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

    # Re-login so the token carries the new company_id and COMPANY_ADMIN role.
    admin = login(client, "admin@acme.co")

    response = admin.post(
        f"{API}/onboarding/organization",
        json={
            "departments": [{"name": "Engineering"}, {"name": "People Ops"}],
            "designations": [{"name": "Software Engineer"}, {"name": "HR Manager"}],
            "locations": [{"name": "Bengaluru Office", "city": "Bengaluru"}],
        },
    )
    assert response.status_code == 201, response.text

    response = admin.post(
        f"{API}/onboarding/work-policy",
        json={
            "working_days": [1, 2, 3, 4, 5],
            "start_time": "09:30:00",
            "end_time": "18:30:00",
            "break_start": "13:00:00",
            "break_end": "14:00:00",
        },
    )
    assert response.status_code == 200, response.text

    response = admin.post(f"{API}/onboarding/leave-policy", json={"leave_types": []})
    assert response.status_code == 200, response.text

    response = admin.post(
        f"{API}/onboarding/admin",
        json={"first_name": "Ada", "last_name": "Admin", "phone": "9000000000"},
    )
    assert response.status_code == 200, response.text

    departments = {d["name"]: d["id"] for d in admin.get(f"{API}/organization/departments").json()}
    designations = {
        d["name"]: d["id"] for d in admin.get(f"{API}/organization/designations").json()
    }
    locations = {loc["name"]: loc["id"] for loc in admin.get(f"{API}/organization/locations").json()}

    # A manager first, so the engineer can report to them.
    response = admin.post(
        f"{API}/employees",
        json={
            "first_name": "Maya",
            "last_name": "Manager",
            "work_email": "maya@acme.co",
            "password": "Password123!",
            "role": "MANAGER",
            "employment": {
                "department_id": departments["Engineering"],
                "designation_id": designations["Software Engineer"],
                "location_id": locations["Bengaluru Office"],
                "joining_date": "2024-01-15",
                "is_manager": True,
            },
        },
    )
    assert response.status_code == 201, response.text
    manager_id = response.json()["employee"]["id"]

    response = admin.post(
        f"{API}/employees",
        json={
            "first_name": "Eli",
            "last_name": "Engineer",
            "work_email": "eli@acme.co",
            "password": "Password123!",
            "role": "EMPLOYEE",
            "employment": {
                "department_id": departments["Engineering"],
                "designation_id": designations["Software Engineer"],
                "location_id": locations["Bengaluru Office"],
                "manager_id": manager_id,
                "joining_date": "2024-03-01",
            },
            "personal": {"date_of_birth": "1996-05-20", "gender": "OTHER"},
        },
    )
    assert response.status_code == 201, response.text
    employee_id = response.json()["employee"]["id"]

    response = admin.post(
        f"{API}/employees",
        json={
            "first_name": "Hana",
            "last_name": "HR",
            "work_email": "hana@acme.co",
            "password": "Password123!",
            "role": "HR",
            "employment": {
                "department_id": departments["People Ops"],
                "designation_id": designations["HR Manager"],
                "joining_date": "2024-02-01",
            },
        },
    )
    assert response.status_code == 201, response.text

    assert admin.post(f"{API}/onboarding/skip-employees").status_code == 200

    return {
        "company_id": company_id,
        "admin": admin,
        "manager_id": manager_id,
        "employee_id": employee_id,
        "departments": departments,
        "locations": locations,
    }


# ---------------------------------------------------------------- auth


def test_signup_rejects_duplicate_email(client):
    signup(client, "dupe@test.co")
    response = client.post(
        f"{API}/auth/signup",
        json={"email": "dupe@test.co", "password": "Password123!", "first_name": "X"},
    )
    assert response.status_code == 409


def test_login_rejects_bad_password(client):
    signup(client, "badpass@test.co")
    response = client.post(
        f"{API}/auth/login", json={"email": "badpass@test.co", "password": "wrong"}
    )
    assert response.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get(f"{API}/employees").status_code == 401


def test_password_reset_round_trip(client):
    signup(client, "reset@test.co")
    response = client.post(f"{API}/auth/forgot-password", json={"email": "reset@test.co"})
    assert response.status_code == 200
    token = response.json()["message"].split("[dev token: ")[1].rstrip("]")

    assert (
        client.post(
            f"{API}/auth/reset-password", json={"token": token, "new_password": "NewPassword1!"}
        ).status_code
        == 200
    )
    login(client, "reset@test.co", "NewPassword1!")


def test_forgot_password_does_not_leak_unknown_emails(client):
    response = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@test.co"})
    assert response.status_code == 200
    assert "dev token" not in response.json()["message"]


# ---------------------------------------------------------------- onboarding


def test_onboarding_completes_and_seeds_defaults(acme):
    admin = acme["admin"]

    company = admin.get(f"{API}/companies/current").json()
    assert company["is_onboarded"] is True
    assert company["onboarding_step"] == "completed"

    leave_types = {lt["code"] for lt in admin.get(f"{API}/organization/leave-types").json()}
    assert {"CL", "SL", "EL", "LWP"} <= leave_types

    policy = admin.get(f"{API}/organization/work-policies").json()[0]
    assert policy["working_days"] == [1, 2, 3, 4, 5]
    assert policy["weekly_off_days"] == [6, 7]

    components = {c["code"] for c in admin.get(f"{API}/payroll/components").json()}
    assert {"BASIC", "HRA", "PF", "PT"} <= components


def test_company_cannot_be_created_twice(acme, client):
    response = acme["admin"].post(
        f"{API}/companies",
        json={
            "name": "Second Corp",
            "industry": "Retail",
            "company_size": "1-10",
            "email": "x@x.co",
            "phone": "1234567890",
            "country": "India",
            "state": "KA",
            "city": "BLR",
            "address": "Somewhere",
            "postal_code": "560002",
        },
    )
    assert response.status_code == 409


# ---------------------------------------------------------------- employees


def test_employee_listing_and_codes(acme):
    page = acme["admin"].get(f"{API}/employees").json()
    assert page["total"] == 4  # admin + manager + engineer + hr
    codes = {row["employee_code"] for row in page["items"]}
    assert len(codes) == 4

    engineer = next(r for r in page["items"] if r["work_email"] == "eli@acme.co")
    assert engineer["department_name"] == "Engineering"
    assert engineer["manager_name"] == "Maya Manager"


def test_employee_search_filter(acme):
    page = acme["admin"].get(f"{API}/employees", params={"search": "maya"}).json()
    assert page["total"] == 1
    assert page["items"][0]["full_name"] == "Maya Manager"


def test_duplicate_work_email_rejected(acme):
    response = acme["admin"].post(
        f"{API}/employees",
        json={
            "first_name": "Clone",
            "work_email": "eli@acme.co",
            "employment": {"joining_date": "2025-01-01"},
            "create_login": False,
        },
    )
    assert response.status_code == 409


def test_csv_import(acme, client):
    csv_body = (
        "first_name,last_name,work_email,department,designation,joining_date,employment_type\n"
        "Ivy,Import,ivy@acme.co,Engineering,Software Engineer,2025-02-03,FULL_TIME\n"
        "Bad,Row,not-an-email,Engineering,Software Engineer,2025-02-03,FULL_TIME\n"
    )
    response = acme["admin"].post(
        f"{API}/employees/import",
        files={"file": ("employees.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 1, body
    assert body["failed"] == 1, body
    assert body["errors"][0]["row"] == 3


# ---------------------------------------------------------------- RBAC + tenancy


def test_employee_cannot_list_all_employees(acme, client):
    employee = login(client, "eli@acme.co")
    page = employee.get(f"{API}/employees").json()
    # Scoped down to just themselves.
    assert page["total"] == 1
    assert page["items"][0]["work_email"] == "eli@acme.co"


def test_employee_cannot_create_employees(acme, client):
    employee = login(client, "eli@acme.co")
    response = employee.post(
        f"{API}/employees",
        json={
            "first_name": "Sneaky",
            "work_email": "sneaky@acme.co",
            "employment": {"joining_date": "2025-01-01"},
            "create_login": False,
        },
    )
    assert response.status_code == 403


def test_manager_sees_only_their_team(acme, client):
    manager = login(client, "maya@acme.co")
    page = manager.get(f"{API}/employees").json()
    emails = {row["work_email"] for row in page["items"]}
    assert emails == {"maya@acme.co", "eli@acme.co"}


def test_employee_cannot_read_another_employee(acme, client):
    employee = login(client, "eli@acme.co")
    response = employee.get(f"{API}/employees/{acme['manager_id']}")
    assert response.status_code == 403


def test_tenant_isolation(acme, client):
    """A second company must never see Acme's data."""
    other_admin = signup(client, "admin@globex.co")
    response = other_admin.post(
        f"{API}/companies",
        json={
            "name": "Globex",
            "industry": "Manufacturing",
            "company_size": "51-200",
            "email": "hello@globex.co",
            "phone": "9998887770",
            "country": "India",
            "state": "Maharashtra",
            "city": "Pune",
            "address": "2 FC Road",
            "postal_code": "411004",
        },
    )
    assert response.status_code == 201
    other_admin = login(client, "admin@globex.co")

    page = other_admin.get(f"{API}/employees").json()
    assert page["total"] == 0

    # Direct id access to another tenant's employee is a 404, not a leak.
    assert other_admin.get(f"{API}/employees/{acme['employee_id']}").status_code == 404
    assert other_admin.get(f"{API}/companies/current").json()["name"] == "Globex"


# ---------------------------------------------------------------- attendance


def test_check_in_check_out_cycle(acme, client):
    employee = login(client, "eli@acme.co")

    status = employee.get(f"{API}/attendance/today").json()
    assert status["checked_in"] is False

    response = employee.post(f"{API}/attendance/check-in", json={"is_wfh": False})
    assert response.status_code == 200, response.text
    assert response.json()["check_in"] is not None

    # A second check-in on the same day is rejected.
    assert employee.post(f"{API}/attendance/check-in", json={}).status_code == 409

    response = employee.post(f"{API}/attendance/check-out", json={})
    assert response.status_code == 200, response.text
    assert response.json()["check_out"] is not None

    assert employee.post(f"{API}/attendance/check-out", json={}).status_code == 409

    status = employee.get(f"{API}/attendance/today").json()
    assert status["checked_in"] and status["checked_out"]


def test_check_out_without_check_in(acme, client):
    hr = login(client, "hana@acme.co")
    assert hr.post(f"{API}/attendance/check-out", json={}).status_code == 400


def test_hr_sees_company_attendance(acme, client):
    hr = login(client, "hana@acme.co")
    page = hr.get(f"{API}/attendance").json()
    assert page["total"] >= 1


def test_hr_can_regularize(acme, client):
    hr = login(client, "hana@acme.co")
    day = (date.today() - timedelta(days=3)).isoformat()
    response = hr.put(
        f"{API}/attendance/{acme['employee_id']}/{day}",
        json={"status": "PRESENT", "remarks": "Missed punch — approved by HR"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_regularized"] is True


# ---------------------------------------------------------------- leave


def test_leave_balances_are_seeded(acme, client):
    employee = login(client, "eli@acme.co")
    balances = {b["leave_type_code"]: b for b in employee.get(f"{API}/leaves/balances").json()}
    assert balances["CL"]["allocated"] == 12
    assert balances["SL"]["allocated"] == 6
    assert balances["EL"]["allocated"] == 15
    assert balances["CL"]["available"] == 12


def test_leave_apply_approve_updates_balance(acme, client):
    employee = login(client, "eli@acme.co")
    manager = login(client, "maya@acme.co")

    casual = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )

    # Pick a Monday-Tuesday next week so the range lands on working days.
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 7)
    response = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": casual["leave_type_id"],
            "from_date": monday.isoformat(),
            "to_date": (monday + timedelta(days=1)).isoformat(),
            "reason": "Family function",
        },
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    assert response.json()["days"] == 2
    assert response.json()["status"] == "PENDING"

    after_apply = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    assert after_apply["pending"] == 2
    assert after_apply["available"] == 10

    pending = manager.get(f"{API}/leaves/requests/pending").json()
    assert any(r["id"] == request_id for r in pending)

    response = manager.post(f"{API}/leaves/{request_id}/approve", json={"comment": "Approved"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"

    after_approve = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    assert after_approve["used"] == 2
    assert after_approve["pending"] == 0
    assert after_approve["available"] == 10


def test_leave_rejected_restores_balance(acme, client):
    employee = login(client, "eli@acme.co")
    manager = login(client, "maya@acme.co")

    sick = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "SL"
    )
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 21)

    response = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": sick["leave_type_id"],
            "from_date": monday.isoformat(),
            "to_date": monday.isoformat(),
            "reason": "Fever",
        },
    )
    request_id = response.json()["id"]

    response = manager.post(
        f"{API}/leaves/{request_id}/reject", json={"comment": "Critical release week"}
    )
    assert response.status_code == 200, response.text

    balance = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "SL"
    )
    assert balance["pending"] == 0
    assert balance["used"] == 0
    assert balance["available"] == 6


def test_leave_rejects_overlapping_dates(acme, client):
    employee = login(client, "eli@acme.co")
    casual = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 7)

    response = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": casual["leave_type_id"],
            "from_date": monday.isoformat(),
            "to_date": monday.isoformat(),
            "reason": "Overlaps the approved leave",
        },
    )
    assert response.status_code == 409


def test_leave_rejects_insufficient_balance(acme, client):
    employee = login(client, "eli@acme.co")
    sick = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "SL"
    )
    start = date.today() + timedelta(days=120)
    response = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": sick["leave_type_id"],
            "from_date": start.isoformat(),
            "to_date": (start + timedelta(days=30)).isoformat(),
            "reason": "Way beyond the 6-day sick leave quota",
        },
    )
    assert response.status_code == 400
    assert "Insufficient balance" in response.json()["detail"]


def test_employee_cannot_approve_own_leave(acme, client):
    employee = login(client, "eli@acme.co")
    casual = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    start = date.today() + timedelta(days=60)
    response = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": casual["leave_type_id"],
            "from_date": start.isoformat(),
            "to_date": start.isoformat(),
            "reason": "Personal work",
        },
    )
    request_id = response.json()["id"]
    assert employee.post(f"{API}/leaves/{request_id}/approve", json={}).status_code == 403


# ---------------------------------------------------------------- holidays


def test_holiday_crud(acme):
    admin = acme["admin"]
    new_year = date(date.today().year + 1, 1, 1)

    response = admin.post(
        f"{API}/holidays",
        json={"name": "New Year", "date": new_year.isoformat(), "holiday_type": "PUBLIC"},
    )
    assert response.status_code == 201, response.text
    holiday_id = response.json()["id"]

    # Same holiday twice is a conflict.
    assert (
        admin.post(
            f"{API}/holidays", json={"name": "New Year", "date": new_year.isoformat()}
        ).status_code
        == 409
    )

    listed = admin.get(f"{API}/holidays", params={"year": new_year.year}).json()
    assert any(h["id"] == holiday_id for h in listed)
    assert admin.delete(f"{API}/holidays/{holiday_id}").status_code == 200


# ---------------------------------------------------------------- payroll


@pytest.fixture(scope="module")
def payroll_ready(acme):
    """Assigns a salary structure to every employee in Acme."""
    admin = acme["admin"]
    structure_id = admin.get(f"{API}/payroll/structures").json()[0]["id"]

    for row in admin.get(f"{API}/employees", params={"page_size": 100}).json()["items"]:
        response = admin.post(
            f"{API}/payroll/salaries/{row['id']}",
            json={
                "structure_id": structure_id,
                "ctc": 1_200_000,
                "effective_from": "2024-01-01",
            },
        )
        assert response.status_code == 201, response.text
    return structure_id


def test_structure_preview_matches_ctc_rules(acme, payroll_ready):
    admin = acme["admin"]
    preview = admin.get(
        f"{API}/payroll/structures/{payroll_ready}/preview", params={"ctc": 1_200_000}
    ).json()
    amounts = {row["code"]: row["monthly_amount"] for row in preview}

    assert amounts["BASIC"] == 50_000  # 50% of 1,200,000 / 12
    assert amounts["HRA"] == 20_000  # 40% of Basic
    assert amounts["PF"] == 6_000  # 12% of Basic
    assert amounts["PT"] == 200


def test_salary_assignment(acme, payroll_ready):
    admin = acme["admin"]
    salaries = admin.get(f"{API}/payroll/salaries/{acme['employee_id']}").json()
    assert len(salaries) == 1
    salary = salaries[0]
    assert salary["ctc"] == 1_200_000
    assert salary["gross_monthly"] > 0
    assert salary["net_monthly"] == pytest.approx(
        salary["gross_monthly"] - salary["deductions_monthly"]
    )


def test_payroll_run_to_payslip(acme, payroll_ready, client):
    admin = acme["admin"]
    last_month = date.today().replace(day=1) - timedelta(days=1)

    response = admin.post(
        f"{API}/payroll/runs", json={"month": last_month.month, "year": last_month.year}
    )
    assert response.status_code == 201, response.text
    run = response.json()
    run_id = run["id"]
    assert run["status"] == "PENDING_REVIEW"
    assert run["employee_count"] >= 4
    assert run["total_net"] > 0

    item = run["items"][0]
    assert item["gross_earnings"] > 0
    assert item["working_days"] > 0
    assert {line["code"] for line in item["earnings_breakdown"]} >= {"BASIC", "HRA"}
    assert {line["code"] for line in item["deductions_breakdown"]} >= {"PF", "PT"}
    assert item["net_pay"] == pytest.approx(
        item["gross_earnings"] - item["total_deductions"], abs=0.05
    )

    # Payslips cannot be generated before approval.
    assert admin.post(f"{API}/payroll/runs/{run_id}/payslips").status_code == 400

    assert admin.post(f"{API}/payroll/runs/{run_id}/approve").status_code == 200

    response = admin.post(f"{API}/payroll/runs/{run_id}/payslips")
    assert response.status_code == 200, response.text
    assert len(response.json()) == run["employee_count"]

    employee = login(client, "eli@acme.co")
    payslips = employee.get(f"{API}/payroll/payslips/me").json()
    assert len(payslips) == 1
    assert payslips[0]["snapshot"]["employee"]["name"] == "Eli Engineer"
    assert payslips[0]["net_pay"] > 0


def test_employee_cannot_read_others_payslip(acme, payroll_ready, client):
    admin = acme["admin"]
    employee = login(client, "eli@acme.co")

    all_slips = admin.get(f"{API}/payroll/runs").json()["items"]
    assert all_slips

    others = [
        p
        for p in admin.get(f"{API}/payroll/runs/{all_slips[0]['id']}/payslips").json()
        if p["employee_id"] != acme["employee_id"]
    ]
    assert employee.get(f"{API}/payroll/payslips/{others[0]['id']}").status_code == 403


def test_duplicate_payroll_period_rejected(acme, payroll_ready):
    admin = acme["admin"]
    last_month = date.today().replace(day=1) - timedelta(days=1)
    response = admin.post(
        f"{API}/payroll/runs", json={"month": last_month.month, "year": last_month.year}
    )
    assert response.status_code == 409


def test_employee_cannot_process_payroll(acme, client):
    employee = login(client, "eli@acme.co")
    assert (
        employee.post(f"{API}/payroll/runs", json={"month": 1, "year": 2025}).status_code == 403
    )


# ---------------------------------------------------------------- documents


def test_document_upload_and_visibility(acme, client):
    admin = acme["admin"]

    response = admin.post(
        f"{API}/documents",
        data={
            "employee_id": acme["employee_id"],
            "title": "Offer Letter",
            "document_type": "OFFER_LETTER",
            "is_visible_to_employee": "true",
        },
        files={"file": ("offer.pdf", b"%PDF-1.4 fake offer letter", "application/pdf")},
    )
    assert response.status_code == 201, response.text
    visible_id = response.json()["id"]

    response = admin.post(
        f"{API}/documents",
        data={
            "employee_id": acme["employee_id"],
            "title": "Internal HR Note",
            "document_type": "OTHER",
            "is_visible_to_employee": "false",
        },
        files={"file": ("note.txt", b"internal only", "text/plain")},
    )
    hidden_id = response.json()["id"]

    employee = login(client, "eli@acme.co")
    mine = employee.get(f"{API}/documents/me").json()
    assert {d["id"] for d in mine} == {visible_id}

    assert employee.get(f"{API}/documents/{visible_id}/download").status_code == 200
    assert employee.get(f"{API}/documents/{hidden_id}/download").status_code == 403


def test_employee_cannot_upload_documents(acme, client):
    employee = login(client, "eli@acme.co")
    response = employee.post(
        f"{API}/documents",
        data={"employee_id": acme["employee_id"], "title": "Self upload"},
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- notifications


def test_notifications_are_generated_and_readable(acme, client):
    manager = login(client, "maya@acme.co")
    page = manager.get(f"{API}/notifications").json()
    assert page["total"] >= 1
    assert any(n["event_type"] == "LEAVE_APPLIED" for n in page["items"])

    before = manager.get(f"{API}/notifications/count").json()
    assert before["unread"] >= 1

    assert manager.post(f"{API}/notifications/read", json={}).status_code == 200
    assert manager.get(f"{API}/notifications/count").json()["unread"] == 0


def test_employee_gets_leave_decision_notification(acme, client):
    employee = login(client, "eli@acme.co")
    events = {n["event_type"] for n in employee.get(f"{API}/notifications").json()["items"]}
    assert "LEAVE_APPROVED" in events
    assert "LEAVE_REJECTED" in events


# ---------------------------------------------------------------- dashboards


def test_hr_dashboard(acme):
    body = acme["admin"].get(f"{API}/dashboard/hr").json()
    assert body["counts"]["total_employees"] >= 4
    assert "pending_leave_requests" in body["pending"]
    assert isinstance(body["upcoming_birthdays"], list)


def test_employee_dashboard(acme, client):
    employee = login(client, "eli@acme.co")
    body = employee.get(f"{API}/dashboard/me").json()
    assert body["full_name"] == "Eli Engineer"
    assert body["today"]["checked_in"] is True
    assert len(body["leave_balances"]) >= 4


def test_employee_cannot_open_hr_dashboard(acme, client):
    employee = login(client, "eli@acme.co")
    assert employee.get(f"{API}/dashboard/hr").status_code == 403


# ---------------------------------------------------------------- reports


def test_reports_json_and_csv(acme, payroll_ready):
    admin = acme["admin"]

    body = admin.get(f"{API}/reports/employees").json()
    assert body["count"] >= 4
    assert "employee_code" in body["columns"]

    csv_response = admin.get(f"{API}/reports/employees", params={"export": True})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "employee_code" in csv_response.text

    for report in ("attendance", "leaves", "payroll"):
        response = admin.get(f"{API}/reports/{report}")
        assert response.status_code == 200, report
        assert "rows" in response.json()

    headcount = admin.get(f"{API}/reports/headcount").json()
    assert any(row["department"] == "Engineering" for row in headcount["rows"])


def test_employee_cannot_view_reports(acme, client):
    employee = login(client, "eli@acme.co")
    assert employee.get(f"{API}/reports/employees").status_code == 403
