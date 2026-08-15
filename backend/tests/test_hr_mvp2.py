"""MVP-2: HR employee lifecycle.

The add-employee wizard (draft → personal → contact → employment → documents →
bank/statutory → review → complete), the company document policy, document
verification, and the HR/document dashboards.
"""

from datetime import date, timedelta

import pytest

from tests.conftest import API, build_company, login

PDF = b"%PDF-1.4 test document"


@pytest.fixture(scope="module")
def hr(client):
    return build_company(client, "wizard", company_name="Wizard Works")


def upload(admin, employee_id, doc_type, name="file.pdf"):
    return admin.post(
        f"{API}/documents",
        data={
            "employee_id": employee_id,
            "title": doc_type.replace("_", " ").title(),
            "document_type": doc_type,
            "is_visible_to_employee": "true",
        },
        files={"file": (name, PDF, "application/pdf")},
    )


# ---------------------------------------------------------------- employee code


def test_employee_code_follows_company_format(hr):
    admin = hr["admin"]
    preview = admin.get(f"{API}/hr/employee-code/preview").json()
    assert len(preview) == 3
    assert all(code.startswith("EMP-") for code in preview), preview
    # Zero-padded and sequential.
    assert preview[0] != preview[1]


def test_code_format_is_configurable(hr):
    admin = hr["admin"]
    response = admin.patch(
        f"{API}/companies/current",
        json={"employee_id_format": "WW/{NUMBER}", "employee_id_padding": 3},
    )
    assert response.status_code == 200
    preview = admin.get(f"{API}/hr/employee-code/preview").json()
    assert preview[0].startswith("WW/"), preview
    assert len(preview[0].split("/")[1]) == 3

    admin.patch(
        f"{API}/companies/current",
        json={"employee_id_format": "EMP-{NUMBER}", "employee_id_padding": 4},
    )


# ---------------------------------------------------------------- document policy


def test_policy_seeds_sensible_defaults(hr):
    policy = hr["admin"].get(f"{API}/hr/document-policy").json()
    by_type = {p["document_type"]: p for p in policy}

    assert by_type["RESUME"]["is_required"] is True
    assert by_type["PAN"]["is_required"] is True
    assert by_type["AADHAAR"]["is_required"] is True
    assert by_type["EXPERIENCE_LETTER"]["is_required"] is False


def test_policy_is_per_company_and_editable(hr, client):
    admin = hr["admin"]
    # Wizard Works decides Aadhaar is not required.
    current = admin.get(f"{API}/hr/document-policy").json()
    updated = [
        {
            "document_type": p["document_type"],
            "is_required": False if p["document_type"] == "AADHAAR" else p["is_required"],
            "tracks_expiry": p["tracks_expiry"],
            "display_order": p["display_order"],
            "is_active": p["is_active"],
        }
        for p in current
    ]
    response = admin.put(f"{API}/hr/document-policy", json={"policies": updated})
    assert response.status_code == 200
    by_type = {p["document_type"]: p for p in response.json()}
    assert by_type["AADHAAR"]["is_required"] is False

    # A different company keeps its own defaults.
    other = build_company(client, "policyco", company_name="Policy Co")
    other_policy = {p["document_type"]: p for p in other["admin"].get(f"{API}/hr/document-policy").json()}
    assert other_policy["AADHAAR"]["is_required"] is True


def test_employee_cannot_change_policy(hr, client):
    employee = login(client, "eli@wizard.co")
    response = employee.put(f"{API}/hr/document-policy", json={"policies": []})
    assert response.status_code == 403


# ---------------------------------------------------------------- the wizard


@pytest.fixture(scope="module")
def draft(hr):
    """Runs the wizard up to (but not including) completion."""
    admin = hr["admin"]

    created = admin.post(
        f"{API}/hr/employees/draft",
        json={"first_name": "Rahul", "last_name": "Sharma", "work_email": "rahul@wizard.co"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_draft_starts_as_draft_with_generated_code(draft):
    assert draft["profile_status"] == "DRAFT"
    assert draft["employee_code"].startswith("EMP-")
    assert draft["next_step"] == "personal"


def test_wizard_steps_save_independently(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    r = admin.patch(
        f"{API}/hr/employees/{eid}/personal",
        json={
            "first_name": "Rahul",
            "middle_name": "Kumar",
            "last_name": "Sharma",
            "date_of_birth": "1996-04-12",
            "gender": "MALE",
            "blood_group": "O+",
            "nationality": "Indian",
        },
    )
    assert r.status_code == 200, r.text

    r = admin.patch(
        f"{API}/hr/employees/{eid}/contact",
        json={
            "personal_email": "rahul.personal@example.com",
            "phone": "9876543210",
            "alternate_phone": "9812345678",
            "city": "Mumbai",
            "emergency_contact_name": "Sunita Sharma",
            "emergency_contact_relation": "Mother",
            "emergency_contact_phone": "9800000000",
        },
    )
    assert r.status_code == 200, r.text

    r = admin.patch(
        f"{API}/hr/employees/{eid}/employment",
        json={
            "joining_date": "2026-09-01",
            "employment_type": "FULL_TIME",
            "work_mode": "HYBRID",
            "department_id": hr["departments"]["Engineering"],
            "designation_id": hr["designations"]["Software Engineer"],
            "location_id": hr["locations"]["Head Office"],
            "manager_id": hr["manager_id"],
        },
    )
    assert r.status_code == 200, r.text

    # Everything landed on the profile.
    profile = admin.get(f"{API}/employees/{eid}").json()
    assert profile["personal"]["date_of_birth"] == "1996-04-12"
    assert profile["employment"]["work_mode"] == "HYBRID"
    assert profile["employment"]["manager_name"] == "Maya Manager"
    assert profile["profile_status"] == "DRAFT"


def test_bank_details_are_masked_for_non_payroll_readers(hr, draft, client):
    admin = hr["admin"]
    eid = draft["employee_id"]

    saved = admin.put(
        f"{API}/hr/employees/{eid}/bank",
        json={
            "bank_name": "HDFC Bank",
            "account_holder_name": "Rahul Sharma",
            "account_number": "50100123454521",
            "ifsc": "HDFC0001234",
            "branch": "Andheri",
        },
    )
    assert saved.status_code == 200, saved.text
    # The person who can run payroll sees the whole number.
    assert saved.json()["account_number"] == "50100123454521"
    assert saved.json()["account_number_masked"] == "XXXX XXXX 4521"

    # A manager has no salary permission — no full number.
    manager = login(client, "maya@wizard.co")
    response = manager.get(f"{API}/hr/employees/{eid}/bank")
    assert response.status_code == 404


def test_statutory_clears_numbers_when_ineligible(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    admin.put(
        f"{API}/hr/employees/{eid}/statutory",
        json={"pan": "ABCDE1234F", "pf_eligible": True, "uan": "100200300400", "esi_eligible": False},
    )
    saved = admin.get(f"{API}/hr/employees/{eid}/statutory").json()
    assert saved["uan"] == "100200300400"

    # Turning eligibility off must not leave a stale UAN behind.
    admin.put(f"{API}/hr/employees/{eid}/statutory", json={"pf_eligible": False})
    cleared = admin.get(f"{API}/hr/employees/{eid}/statutory").json()
    assert cleared["uan"] is None
    assert cleared["pf_number"] is None
    assert cleared["pan"] == "ABCDE1234F"  # untouched


# ---------------------------------------------------------------- documents


def test_uploads_start_pending_and_appear_on_the_checklist(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    response = upload(admin, eid, "RESUME", "rahul_cv.pdf")
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "PENDING"

    checklist = admin.get(f"{API}/hr/employees/{eid}/documents/checklist").json()
    rows = {r["document_type"]: r for r in checklist["rows"]}
    assert rows["RESUME"]["missing"] is False
    assert rows["RESUME"]["status"] == "PENDING"
    assert rows["PAN"]["missing"] is True
    assert checklist["complete"] is False


def test_verify_and_reject_with_reason(hr, draft, client):
    admin = hr["admin"]
    eid = draft["employee_id"]

    pan = upload(admin, eid, "PAN").json()
    rejected = admin.post(
        f"{API}/hr/documents/{pan['id']}/reject",
        json={"reason": "Document is not readable."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "Document is not readable."

    # Rejection must be explained — an empty reason is refused.
    assert admin.post(f"{API}/hr/documents/{pan['id']}/reject", json={"reason": ""}).status_code == 422

    verified = admin.post(f"{API}/hr/documents/{pan['id']}/verify", json={})
    assert verified.status_code == 200
    assert verified.json()["status"] == "VERIFIED"
    assert verified.json()["rejection_reason"] is None
    assert verified.json()["verified_at"]


def test_employee_is_told_when_a_document_is_rejected(hr, draft, client):
    admin = hr["admin"]
    employee = login(client, "eli@wizard.co")

    me = employee.get(f"{API}/employees/me").json()
    doc = upload(admin, me["id"], "AADHAAR").json()
    admin.post(f"{API}/hr/documents/{doc['id']}/reject", json={"reason": "Blurred scan"})

    notes = employee.get(f"{API}/notifications").json()["items"]
    assert any("rejected" in n["title"].lower() for n in notes), [n["title"] for n in notes]


def test_expiry_is_reflected_on_the_checklist(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    permit = upload(admin, eid, "WORK_PERMIT").json()
    admin.post(
        f"{API}/hr/documents/{permit['id']}/verify",
        json={"expiry_date": str(date.today() - timedelta(days=1))},
    )
    checklist = admin.get(f"{API}/hr/employees/{eid}/documents/checklist").json()
    row = next(r for r in checklist["rows"] if r["document_type"] == "WORK_PERMIT")
    assert row["status"] == "EXPIRED"


# ---------------------------------------------------------------- review + complete


def test_review_blocks_completion_until_required_documents_verified(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    review = admin.get(f"{API}/hr/employees/{eid}/review").json()
    assert review["can_complete"] is False
    assert review["blocking"], review
    # Resume is uploaded but not yet verified, offer letter not uploaded at all.
    joined = " ".join(review["blocking"]).lower()
    assert "resume" in joined or "offer letter" in joined

    blocked = admin.post(f"{API}/hr/employees/{eid}/complete")
    assert blocked.status_code == 400
    assert "cannot be completed" in blocked.json()["detail"]


def test_completes_once_every_required_document_is_verified(hr, draft):
    admin = hr["admin"]
    eid = draft["employee_id"]

    policy = admin.get(f"{API}/hr/document-policy").json()
    required = [p["document_type"] for p in policy if p["is_required"] and p["is_active"]]

    checklist = admin.get(f"{API}/hr/employees/{eid}/documents/checklist").json()
    existing = {r["document_type"]: r for r in checklist["rows"]}

    for doc_type in required:
        row = existing.get(doc_type)
        doc_id = row["document_id"] if row and row["document_id"] else upload(admin, eid, doc_type).json()["id"]
        admin.post(f"{API}/hr/documents/{doc_id}/verify", json={})

    review = admin.get(f"{API}/hr/employees/{eid}/review").json()
    assert review["can_complete"] is True, review["blocking"]

    completed = admin.post(f"{API}/hr/employees/{eid}/complete")
    assert completed.status_code == 200, completed.text
    assert completed.json()["profile_status"] == "COMPLETE"


def test_admin_can_force_complete_a_draft(hr):
    admin = hr["admin"]
    created = admin.post(
        f"{API}/hr/employees/draft",
        json={"first_name": "Forced", "last_name": "Case", "work_email": "forced@wizard.co"},
    ).json()
    eid = created["employee_id"]
    admin.patch(f"{API}/hr/employees/{eid}/employment", json={"joining_date": "2026-10-01"})

    assert admin.post(f"{API}/hr/employees/{eid}/complete").status_code == 400
    forced = admin.post(f"{API}/hr/employees/{eid}/complete", params={"force": True})
    assert forced.status_code == 200, forced.text
    assert forced.json()["profile_status"] == "COMPLETE"


# ---------------------------------------------------------------- dashboards


def test_document_register_filters(hr):
    admin = hr["admin"]
    page = admin.get(f"{API}/hr/documents", params={"status": "VERIFIED"}).json()
    assert all(d["status"] == "VERIFIED" for d in page["items"])

    typed = admin.get(f"{API}/hr/documents", params={"document_type": "RESUME"}).json()
    assert all(d["document_type"] == "RESUME" for d in typed["items"])


def test_document_dashboard_kpis(hr):
    data = hr["admin"].get(f"{API}/hr/documents/dashboard").json()
    k = data["kpis"]
    assert k["total"] == k["verified"] + k["pending"] + k["rejected"] + k["expired"]
    assert isinstance(data["employees_with_missing_required"], int)


def test_hr_overview(hr):
    data = hr["admin"].get(f"{API}/hr/overview").json()
    assert data["counts"]["total_employees"] >= 4
    assert "pending_documents" in data["counts"]
    assert isinstance(data["upcoming_joiners"], list)
    assert isinstance(data["recent_employees"], list)


def test_employee_cannot_reach_hr_endpoints(hr, client):
    employee = login(client, "eli@wizard.co")
    assert employee.get(f"{API}/hr/overview").status_code == 403
    assert employee.get(f"{API}/hr/documents/dashboard").status_code == 403
    assert employee.post(
        f"{API}/hr/employees/draft",
        json={"first_name": "X", "work_email": "x@wizard.co"},
    ).status_code == 403


def test_employee_sees_own_checklist_only(hr, client):
    employee = login(client, "eli@wizard.co")
    me = employee.get(f"{API}/employees/me").json()

    own = employee.get(f"{API}/hr/employees/{me['id']}/documents/checklist")
    assert own.status_code == 200

    other = employee.get(f"{API}/hr/employees/{hr['manager_id']}/documents/checklist")
    assert other.status_code == 404
