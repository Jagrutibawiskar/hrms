"""Covers the second batch of features.

Geofenced attendance, the monthly regularization cap, admin leave editing,
leave attachments filing into Documents, compliance settings driving payroll
deductions, and the company logo.
"""

from datetime import date, timedelta

import pytest

from tests.conftest import API, build_company, login


@pytest.fixture(scope="module")
def acme(client):
    """This module's own tenant, so it never collides with test_flow's company."""
    return build_company(client, "nova", company_name="Nova Labs")


# ---------------------------------------------------------------- geofence


def test_geofence_off_by_default(acme, client):
    """Existing companies keep working — nothing is fenced until it's switched on."""
    company = acme["admin"].get(f"{API}/companies/current").json()
    assert company["geofence_enabled"] is False

    employee = login(client, "eli@nova.co")
    today = employee.get(f"{API}/attendance/today").json()
    assert today["geofence_enabled"] is False


def test_geofence_blocks_far_away_and_allows_nearby(acme, client):
    admin = acme["admin"]
    location_id = acme["locations"]["Head Office"]

    # Pin the office and switch the fence on.
    office = {"latitude": 12.9716, "longitude": 77.5946, "geofence_radius_m": 100}
    assert admin.patch(f"{API}/organization/locations/{location_id}", json=office).status_code == 200
    assert admin.patch(f"{API}/companies/current", json={"geofence_enabled": True}).status_code == 200

    employee = login(client, "eli@nova.co")
    today = employee.get(f"{API}/attendance/today").json()
    assert today["geofence_enabled"] is True
    assert today["geofence_radius_m"] == 100

    # ~2 km away: refused, and the message says how far off they are.
    far = employee.post(
        f"{API}/attendance/check-in",
        json={"is_wfh": False, "latitude": 12.9900, "longitude": 77.5946},
    )
    assert far.status_code == 400
    assert "must be within 100 m" in far.json()["detail"]

    # No coordinates at all: also refused, with a clear instruction.
    missing = employee.post(f"{API}/attendance/check-in", json={"is_wfh": False})
    assert missing.status_code == 400
    assert "Location access is required" in missing.json()["detail"]

    # ~20 m away: allowed.
    near = employee.post(
        f"{API}/attendance/check-in",
        json={"is_wfh": False, "latitude": 12.97178, "longitude": 77.5946},
    )
    assert near.status_code == 200, near.text

    # Turn it back off so later tests are unaffected.
    admin.patch(f"{API}/companies/current", json={"geofence_enabled": False})


def test_wfh_is_exempt_from_the_fence(acme, client):
    admin = acme["admin"]
    admin.patch(f"{API}/companies/current", json={"geofence_enabled": True})

    hr = login(client, "hana@nova.co")
    response = hr.post(f"{API}/attendance/check-in", json={"is_wfh": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "WFH"

    admin.patch(f"{API}/companies/current", json={"geofence_enabled": False})


# ---------------------------------------------------------------- regularization cap


def test_regularization_capped_at_three_per_month(acme):
    admin = acme["admin"]
    employee_id = acme["employee_id"]

    company = admin.get(f"{API}/companies/current").json()
    assert company["max_regularizations_per_month"] == 3

    # Three corrections in the same month succeed.
    base = date.today().replace(day=1) + timedelta(days=10)
    for offset in range(3):
        day = (base + timedelta(days=offset)).isoformat()
        response = admin.put(
            f"{API}/attendance/{employee_id}/{day}",
            json={"status": "PRESENT", "remarks": f"Missed punch {offset}"},
        )
        assert response.status_code == 200, response.text

    # The fourth is refused.
    fourth = (base + timedelta(days=3)).isoformat()
    response = admin.put(
        f"{API}/attendance/{employee_id}/{fourth}",
        json={"status": "PRESENT", "remarks": "One too many"},
    )
    assert response.status_code == 400
    assert "used all 3 attendance regularizations" in response.json()["detail"]

    # Re-editing an already-regularized day is still allowed — it costs nothing extra.
    again = admin.put(
        f"{API}/attendance/{employee_id}/{base.isoformat()}",
        json={"status": "WFH", "remarks": "Corrected again"},
    )
    assert again.status_code == 200, again.text


def test_regularization_limit_is_configurable(acme):
    admin = acme["admin"]
    response = admin.patch(f"{API}/companies/current", json={"max_regularizations_per_month": 5})
    assert response.status_code == 200
    assert response.json()["max_regularizations_per_month"] == 5
    admin.patch(f"{API}/companies/current", json={"max_regularizations_per_month": 3})


# ---------------------------------------------------------------- leave editing


def test_admin_can_edit_leave_and_balance_follows(acme, client):
    admin = acme["admin"]
    employee = login(client, "eli@nova.co")

    casual = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 42)

    created = employee.post(
        f"{API}/leaves",
        json={
            "leave_type_id": casual["leave_type_id"],
            "from_date": monday.isoformat(),
            "to_date": (monday + timedelta(days=2)).isoformat(),
            "reason": "Three days off",
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["days"] == 3

    before = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    assert before["pending"] == 3

    # Shorten it to one day; the reserved balance must shrink with it.
    edited = admin.patch(
        f"{API}/leaves/{request_id}",
        json={"to_date": monday.isoformat(), "edit_note": "Returned early"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["days"] == 1

    after = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "CL"
    )
    assert after["pending"] == 1
    assert after["available"] == before["available"] + 2


def test_employee_cannot_edit_leave(acme, client):
    admin = acme["admin"]
    employee = login(client, "eli@nova.co")

    pending = admin.get(f"{API}/leaves/requests", params={"status": "PENDING"}).json()["items"]
    assert pending, "expected a pending request to exist"

    response = employee.patch(
        f"{API}/leaves/{pending[0]['id']}", json={"reason": "Trying to change this"}
    )
    assert response.status_code == 403


def test_leave_response_no_longer_carries_a_phone_number(acme, client):
    employee = login(client, "eli@nova.co")
    page = employee.get(f"{API}/leaves/me").json()
    assert page["items"], "expected at least one leave request"
    assert "contact_during_leave" not in page["items"][0]


# ---------------------------------------------------------------- leave attachment


def test_leave_attachment_is_filed_into_documents(acme, client):
    employee = login(client, "eli@nova.co")
    admin = acme["admin"]

    sick = next(
        b for b in employee.get(f"{API}/leaves/balances").json() if b["leave_type_code"] == "SL"
    )
    day = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 + 63)

    before = len(admin.get(f"{API}/documents/employee/{acme['employee_id']}").json())

    response = employee.post(
        f"{API}/leaves/with-attachment",
        data={
            "leave_type_id": sick["leave_type_id"],
            "from_date": day.isoformat(),
            "to_date": day.isoformat(),
            "reason": "Medical certificate attached",
        },
        files={"file": ("certificate.pdf", b"%PDF-1.4 medical certificate", "application/pdf")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["attachment_path"]

    documents = admin.get(f"{API}/documents/employee/{acme['employee_id']}").json()
    assert len(documents) == before + 1

    filed = next(d for d in documents if d["document_type"] == "LEAVE_ATTACHMENT")
    assert filed["file_name"] == "certificate.pdf"
    assert filed["is_visible_to_employee"] is True

    # The employee can see and download their own certificate.
    mine = employee.get(f"{API}/documents/me").json()
    assert any(d["document_type"] == "LEAVE_ATTACHMENT" for d in mine)


# ---------------------------------------------------------------- compliance


def test_compliance_defaults_and_update(acme):
    admin = acme["admin"]

    created = admin.get(f"{API}/compliance")
    assert created.status_code == 200
    body = created.json()
    assert body["pf_enabled"] is True
    assert body["pf_employee_rate"] == 12
    assert body["esi_wage_ceiling"] == 21000

    updated = admin.put(
        f"{API}/compliance",
        json={"pan": "AAACN1234F", "pf_number": "KA/BNG/12345", "tds_enabled": True, "tan": "BLRA12345B"},
    )
    assert updated.status_code == 200
    assert updated.json()["pan"] == "AAACN1234F"


def test_compliance_status_flags_missing_details(acme):
    admin = acme["admin"]
    admin.put(f"{API}/compliance", json={"pan": None, "esi_enabled": True, "esi_number": None})

    status = admin.get(f"{API}/compliance/status").json()
    assert status["ready"] is False
    labels = {c["label"]: c for c in status["checks"]}
    assert labels["Company PAN"]["ok"] is False
    assert labels["Employee State Insurance"]["ok"] is False

    # Disabling a scheme counts as compliant — nothing left to file.
    admin.put(f"{API}/compliance", json={"esi_enabled": False})
    status = admin.get(f"{API}/compliance/status").json()
    assert {c["label"]: c for c in status["checks"]}["Employee State Insurance"]["ok"] is True


def test_employee_cannot_change_compliance(acme, client):
    employee = login(client, "eli@nova.co")
    assert employee.put(f"{API}/compliance", json={"pan": "HACKED1234X"}).status_code == 403


# ---------------------------------------------------------------- logo


def test_logo_upload_and_removal(acme):
    admin = acme["admin"]
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = admin.post(
        f"{API}/companies/current/logo",
        files={"file": ("logo.png", png, "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["logo_url"], "logo_url should be returned for the browser"
    assert response.json()["logo_path"]

    assert admin.get(f"{API}/companies/current").json()["logo_url"]
    assert admin.delete(f"{API}/companies/current/logo").status_code == 200
    assert admin.get(f"{API}/companies/current").json()["logo_url"] is None


def test_logo_rejects_non_images(acme):
    response = acme["admin"].post(
        f"{API}/companies/current/logo",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------- payroll


@pytest.fixture(scope="module")
def salaried(acme):
    admin = acme["admin"]
    structure_id = admin.get(f"{API}/payroll/structures").json()[0]["id"]
    for row in admin.get(f"{API}/employees", params={"page_size": 100}).json()["items"]:
        admin.post(
            f"{API}/payroll/salaries/{row['id']}",
            json={"structure_id": structure_id, "ctc": 1_200_000, "effective_from": "2024-01-01"},
        )
    return structure_id


def test_payroll_reports_why_lop_was_charged(acme, salaried):
    admin = acme["admin"]
    two_months_ago = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)

    response = admin.post(
        f"{API}/payroll/runs", json={"month": two_months_ago.month, "year": two_months_ago.year}
    )
    assert response.status_code == 201, response.text

    item = response.json()["items"][0]
    assert "lop_breakdown" in item
    breakdown = item["lop_breakdown"]
    # Every LOP source is accounted for, so the number is explainable.
    for key in ("absent_days", "unpaid_leave_days", "half_days", "paid_leave_days"):
        assert key in breakdown
    assert item["paid_days"] + item["lop_days"] == pytest.approx(item["working_days"])


def test_disabling_pf_removes_it_from_the_next_run(acme, salaried):
    admin = acme["admin"]
    period = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
    month, year = period.month, period.year

    admin.put(f"{API}/compliance", json={"pf_enabled": True})
    with_pf = admin.post(f"{API}/payroll/runs", json={"month": month, "year": year}).json()
    codes = {line["code"] for line in with_pf["items"][0]["deductions_breakdown"]}
    assert "PF" in codes

    admin.put(f"{API}/compliance", json={"pf_enabled": False})
    without_pf = admin.post(f"{API}/payroll/runs", json={"month": month, "year": year}).json()
    codes = {line["code"] for line in without_pf["items"][0]["deductions_breakdown"]}
    assert "PF" not in codes
    assert without_pf["items"][0]["net_pay"] > with_pf["items"][0]["net_pay"]

    admin.put(f"{API}/compliance", json={"pf_enabled": True})


def test_payslip_snapshot_carries_company_branding(acme, salaried):
    admin = acme["admin"]
    period = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)

    response = admin.post(
        f"{API}/payroll/runs", json={"month": period.month, "year": period.year}
    )
    if response.status_code == 409:
        # An earlier test already approved this period; reuse that run.
        run = next(
            r
            for r in admin.get(f"{API}/payroll/runs").json()["items"]
            if r["month"] == period.month and r["year"] == period.year
        )
    else:
        assert response.status_code == 201, response.text
        run = response.json()

    if run["status"] == "PENDING_REVIEW":
        admin.post(f"{API}/payroll/runs/{run['id']}/approve")
    payslips = admin.post(f"{API}/payroll/runs/{run['id']}/payslips").json()

    snapshot = payslips[0]["snapshot"]
    assert snapshot["company"]["name"] == "Nova Labs"
    assert "logo_path" in snapshot["company"]
    # The payslip explains its own LOP.
    assert "absent_days" in snapshot["days"]
