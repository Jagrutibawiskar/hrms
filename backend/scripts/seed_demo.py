import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

ENV_FILE = BACKEND_DIR / ".env"
if not ENV_FILE.exists():
    ENV_FILE.write_text(
        "DATABASE_URL=sqlite:///./hrms.db\n"
        "SECRET_KEY=demo-secret-change-me\n"
        "DEBUG=true\n"
        "AUTO_CREATE_TABLES=true\n"
        "REQUIRE_EMAIL_VERIFICATION=false\n"
        "CORS_ORIGINS=http://localhost:3000\n",
        encoding="utf-8",
    )
    print(f"Created {ENV_FILE}")

if "--reset" in sys.argv:
    for name in ("hrms.db", "hrms.db-journal"):
        target = BACKEND_DIR / name
        if target.exists():
            target.unlink()
            print(f"Removed {name}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.seed import seed_roles_and_permissions  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Attendance, Base, Employee  # noqa: E402
from app.models.enums import AttendanceStatus  # noqa: E402
from app.services.calendar_service import (  # noqa: E402
    employee_location_id,
    get_work_policy,
    holiday_map,
    is_working_day,
)

API = "/api/v1"
PASSWORD = "Password123!"
# The server works in UTC (`app.utils.dates.today()`), so the seed must too.
# Using the local date instead makes them disagree either side of midnight, which
# silently backfills "today" and leaves every demo employee already checked in.
TODAY = datetime.now(timezone.utc).date()


class Session:
    def __init__(self, client, token):
        self.client, self.h = client, {"Authorization": f"Bearer {token}"}

    def post(self, url, **kw):
        return self._check(self.client.post(url, headers=self.h, **kw))

    def get(self, url, **kw):
        return self._check(self.client.get(url, headers=self.h, **kw))

    def put(self, url, **kw):
        return self._check(self.client.put(url, headers=self.h, **kw))

    def patch(self, url, **kw):
        return self._check(self.client.patch(url, headers=self.h, **kw))

    @staticmethod
    def _check(response):
        if response.status_code >= 400:
            raise SystemExit(f"{response.request.method} {response.request.url}\n{response.text}")
        return response


def login(client, email) -> Session:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise SystemExit(f"Login failed for {email}: {r.text}")
    return Session(client, r.json()["tokens"]["access_token"])


EMPLOYEES = [
    # first, last, dept, designation, role, manager?, joined, dob
    ("Maya",   "Menon",    "Engineering", "Engineering Manager", "MANAGER",  None,    "2022-04-11", "1988-11-02"),
    ("Hana",   "Kapoor",   "People Ops",  "HR Manager",          "HR",       None,    "2022-07-01", "1990-03-17"),
    ("Eli",    "Fernandes","Engineering", "Senior Engineer",     "EMPLOYEE", "Maya",  "2023-01-09", "1993-05-20"),
    ("Rohan",  "Sharma",   "Engineering", "Software Engineer",   "EMPLOYEE", "Maya",  "2023-06-19", "1997-08-14"),
    ("Priya",  "Nair",     "Engineering", "QA Engineer",         "EMPLOYEE", "Maya",  "2024-02-05", "1996-01-28"),
    ("Arjun",  "Reddy",    "Sales",       "Sales Executive",     "EMPLOYEE", None,    "2024-03-18", "1995-09-09"),
    ("Sana",   "Iqbal",    "People Ops",  "HR Executive",        "EMPLOYEE", "Hana",  "2024-08-12", "1998-12-03"),
    ("Vikram", "Desai",    "Finance",     "Accountant",          "EMPLOYEE", None,    "2024-11-04", "1991-06-25"),
]

HOLIDAYS = [
    ("New Year's Day", date(TODAY.year, 1, 1)),
    ("Republic Day", date(TODAY.year, 1, 26)),
    ("Holi", date(TODAY.year, 3, 14)),
    ("Independence Day", date(TODAY.year, 8, 15)),
    ("Gandhi Jayanti", date(TODAY.year, 10, 2)),
    ("Diwali", date(TODAY.year, 11, 1)),
    ("Christmas", date(TODAY.year, 12, 25)),
]


def build():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_roles_and_permissions(db)

    with TestClient(app) as client:
        # ---------------------------------------------------------- account
        r = client.post(
            f"{API}/auth/signup",
            json={
                "email": "admin@nimbus.com",
                "password": PASSWORD,
                "first_name": "Ada",
                "last_name": "Sharma",
                "phone": "9800000001",
            },
        )
        if r.status_code == 409:
            print("Demo data already exists. Re-run with --reset to rebuild.")
            return
        if r.status_code != 201:
            raise SystemExit(r.text)
        admin = Session(client, r.json()["tokens"]["access_token"])
        print("✓ Signed up admin@nimbus.com")

        # ---------------------------------------------------------- company
        admin.post(
            f"{API}/companies",
            json={
                "name": "Nimbus Technologies",
                "industry": "Software",
                "company_size": "11-50",
                "company_type": "Private Limited",
                "email": "hello@nimbus.com",
                "phone": "08040001234",
                "website": "https://nimbus.example",
                "country": "India",
                "state": "Karnataka",
                "city": "Bengaluru",
                "address": "4th Floor, Prestige Tower, MG Road",
                "postal_code": "560001",
            },
        )
        # Token must be reissued — it still carries company_id: null.
        admin = login(client, "admin@nimbus.com")
        print("✓ Created company: Nimbus Technologies")

        # ---------------------------------------------------------- onboarding
        admin.post(
            f"{API}/onboarding/organization",
            json={
                "departments": [
                    {"name": "Engineering", "code": "ENG"},
                    {"name": "People Ops", "code": "HR"},
                    {"name": "Sales", "code": "SLS"},
                    {"name": "Finance", "code": "FIN"},
                ],
                "designations": [
                    {"name": "Engineering Manager", "level": 5},
                    {"name": "Senior Engineer", "level": 4},
                    {"name": "Software Engineer", "level": 3},
                    {"name": "QA Engineer", "level": 3},
                    {"name": "HR Manager", "level": 5},
                    {"name": "HR Executive", "level": 2},
                    {"name": "Sales Executive", "level": 3},
                    {"name": "Accountant", "level": 3},
                ],
                "locations": [
                    {"name": "Bengaluru HQ", "city": "Bengaluru", "state": "Karnataka",
                     "country": "India", "is_headquarters": True},
                    {"name": "Pune Office", "city": "Pune", "state": "Maharashtra",
                     "country": "India"},
                ],
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
                "full_day_hours": 8,
                "half_day_hours": 4,
                "late_grace_minutes": 15,
            },
        )
        admin.post(f"{API}/onboarding/leave-policy", json={"leave_types": []})
        admin.post(
            f"{API}/onboarding/admin",
            json={
                "first_name": "Ada",
                "last_name": "Sharma",
                "phone": "9800000001",
                "designation_name": "Founder & CEO",
                "joining_date": "2022-01-03",
            },
        )
        print("✓ Onboarding steps 2-5 complete")

        depts = {d["name"]: d["id"] for d in admin.get(f"{API}/organization/departments").json()}
        desigs = {d["name"]: d["id"] for d in admin.get(f"{API}/organization/designations").json()}
        locs = {loc["name"]: loc["id"] for loc in admin.get(f"{API}/organization/locations").json()}

        # ---------------------------------------------------------- employees
        by_name: dict[str, int] = {}
        for first, last, dept, desig, role, mgr, joined, dob in EMPLOYEES:
            body = {
                "first_name": first,
                "last_name": last,
                "work_email": f"{first.lower()}@nimbus.com",
                "password": PASSWORD,
                "role": role,
                "employment": {
                    "department_id": depts[dept],
                    "designation_id": desigs[desig],
                    "location_id": locs["Bengaluru HQ"],
                    "manager_id": by_name.get(mgr) if mgr else None,
                    "joining_date": joined,
                    "employment_type": "FULL_TIME",
                    "is_manager": role in ("MANAGER", "HR"),
                },
                "personal": {
                    "date_of_birth": dob,
                    "gender": "FEMALE" if first in ("Maya", "Hana", "Priya", "Sana") else "MALE",
                    "phone": f"98{random.randint(10000000, 99999999)}",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "country": "India",
                    "emergency_contact_name": f"{last} Family",
                    "emergency_contact_relation": "Spouse",
                    "emergency_contact_phone": f"98{random.randint(10000000, 99999999)}",
                },
            }
            by_name[first] = admin.post(f"{API}/employees", json=body).json()["employee"]["id"]
        admin.post(f"{API}/onboarding/skip-employees")
        print(f"✓ Added {len(EMPLOYEES)} employees + admin, onboarding complete")

        # ---------------------------------------------------------- holidays
        admin.post(
            f"{API}/holidays/bulk",
            json=[
                {"name": name, "date": day.isoformat(), "holiday_type": "PUBLIC"}
                for name, day in HOLIDAYS
            ],
        )
        print(f"✓ Loaded {len(HOLIDAYS)} holidays")

        # ---------------------------------------------------------- salaries
        structure_id = admin.get(f"{API}/payroll/structures").json()[0]["id"]
        ctc_by_designation = {
            "Founder & CEO": 4_800_000,
            "Engineering Manager": 3_200_000,
            "HR Manager": 2_400_000,
            "Senior Engineer": 2_200_000,
            "Software Engineer": 1_400_000,
            "QA Engineer": 1_200_000,
            "Sales Executive": 1_000_000,
            "HR Executive": 800_000,
            "Accountant": 900_000,
        }
        roster = admin.get(f"{API}/employees", params={"page_size": 100}).json()["items"]
        for row in roster:
            ctc = ctc_by_designation.get(row["designation_name"], 900_000)
            admin.post(
                f"{API}/payroll/salaries/{row['id']}",
                json={
                    "structure_id": structure_id,
                    "ctc": ctc,
                    "effective_from": "2024-01-01",
                    "payment_mode": "BANK_TRANSFER",
                    "bank_account_number": f"5011{random.randint(100000, 999999)}",
                    "bank_ifsc": "HDFC0001234",
                },
            )
        print(f"✓ Assigned salary structures to {len(roster)} employees")

        # ---------------------------------------------------------- attendance history
        created = seed_attendance(days_back=75)
        print(f"✓ Generated {created} attendance records (last ~75 days)")

        # ---------------------------------------------------------- leave
        seed_leave(client, by_name)

        # ---------------------------------------------------------- payroll (2 months ago)
        two_months_ago = (TODAY.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
        run = admin.post(
            f"{API}/payroll/runs",
            json={"month": two_months_ago.month, "year": two_months_ago.year},
        ).json()
        admin.post(f"{API}/payroll/runs/{run['id']}/approve")
        slips = admin.post(f"{API}/payroll/runs/{run['id']}/payslips").json()
        print(
            f"✓ Payroll {two_months_ago.month:02d}/{two_months_ago.year} approved, "
            f"{len(slips)} payslips generated"
        )

        # ---------------------------------------------------------- documents
        admin.post(
            f"{API}/documents",
            data={
                "employee_id": by_name["Eli"],
                "title": "Offer Letter",
                "document_type": "OFFER_LETTER",
                "is_visible_to_employee": "true",
            },
            files={"file": ("offer_letter.pdf", b"%PDF-1.4 Nimbus offer letter", "application/pdf")},
        )
        admin.post(
            f"{API}/documents",
            data={
                "employee_id": by_name["Eli"],
                "title": "Background Check (HR only)",
                "document_type": "OTHER",
                "is_visible_to_employee": "false",
            },
            files={"file": ("bgv.txt", b"internal HR record", "text/plain")},
        )
        print("✓ Uploaded sample documents")

        # ---------------------------------------------------------- compliance
        admin.put(
            f"{API}/compliance",
            json={
                "pan": "AAACN1234F",
                "pf_number": "KA/BNG/0045678",
                "esi_number": "31000123450000999",
                "pt_state": "Karnataka",
                "gstin": "29AAACN1234F1Z5",
                "tds_enabled": True,
                "tan": "BLRN01234C",
            },
        )
        print("✓ Compliance details filled in")

        # ---------------------------------------------------------- geofence
        locations = admin.get(f"{API}/organization/locations").json()
        hq = next((loc for loc in locations if loc["is_headquarters"]), locations[0])
        admin.patch(
            f"{API}/organization/locations/{hq['id']}",
            # MG Road, Bengaluru — matches the company address.
            json={"latitude": 12.9716, "longitude": 77.5946, "geofence_radius_m": 100},
        )
        print(f"✓ Pinned {hq['name']} for geofencing (100 m) — switch it on in Settings")

        # ---------------------------------------------------------- second company
        # Gives the executive's company switcher something to switch between.
        second = signup_company(client)
        print(f"✓ Created a second company ({second}) for the executive demo")

    create_executive()
    summary(TODAY)


def signup_company(client) -> str:
    """A minimal second tenant, so the executive dropdown has two options."""
    response = client.post(
        f"{API}/auth/signup",
        json={
            "email": "admin@orbit.com",
            "password": PASSWORD,
            "first_name": "Omar",
            "last_name": "Khan",
        },
    )
    token = response.json()["tokens"]["access_token"]
    session = Session(client, token)
    session.post(
        f"{API}/companies",
        json={
            "name": "Orbit Retail",
            "industry": "Retail",
            "company_size": "51-200",
            "email": "hello@orbit.com",
            "phone": "02240001234",
            "country": "India",
            "state": "Maharashtra",
            "city": "Mumbai",
            "address": "9 Marine Drive",
            "postal_code": "400020",
        },
    )
    fresh = login(client, "admin@orbit.com")
    fresh.post(
        f"{API}/onboarding/organization",
        json={"departments": [{"name": "Store Ops"}], "designations": [{"name": "Store Manager"}],
              "locations": [{"name": "Mumbai Store", "city": "Mumbai"}]},
    )
    fresh.post(f"{API}/onboarding/work-policy", json={
        "working_days": [1, 2, 3, 4, 5, 6], "start_time": "10:00:00", "end_time": "19:00:00"})
    fresh.post(f"{API}/onboarding/leave-policy", json={"leave_types": []})
    fresh.post(f"{API}/onboarding/admin", json={
        "first_name": "Omar", "last_name": "Khan", "phone": "9820011223"})
    fresh.post(f"{API}/onboarding/skip-employees")
    return "Orbit Retail"


def create_executive() -> None:
    """Platform-level account that can view any company."""
    from app.core.security import hash_password
    from app.models import User
    from app.models.enums import RoleName
    from app.services import auth_service

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "exec@nimbus.com"))
        if user is None:
            user = User(
                email="exec@nimbus.com",
                password_hash=hash_password(PASSWORD),
                first_name="Sovik",
                last_name="Roy",
                company_id=None,
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
            db.flush()
        auth_service.assign_role(db, user, RoleName.SUPER_ADMIN)
        db.commit()
    print("✓ Executive account ready (exec@nimbus.com)")


def seed_attendance(days_back: int) -> int:
    """Backdated attendance written directly — check-in/out only works for today."""
    created = 0
    with SessionLocal() as db:
        employees = list(db.scalars(select(Employee)))

        for employee in employees:
            policy = get_work_policy(db, employee.company_id, employee)
            joined = employee.employment.joining_date if employee.employment else TODAY
            holidays = holiday_map(
                db,
                employee.company_id,
                TODAY - timedelta(days=days_back),
                TODAY,
                employee_location_id(employee),
            )

            for offset in range(days_back, 0, -1):
                day = TODAY - timedelta(days=offset)
                if day < joined:
                    continue

                existing = db.scalar(
                    select(Attendance).where(
                        Attendance.employee_id == employee.id, Attendance.date == day
                    )
                )
                if existing is not None:
                    continue

                if day in holidays:
                    status, check_in, check_out, hours, late = (
                        AttendanceStatus.HOLIDAY, None, None, 0, 0
                    )
                elif not is_working_day(policy, day):
                    status, check_in, check_out, hours, late = (
                        AttendanceStatus.WEEKEND, None, None, 0, 0
                    )
                else:
                    roll = random.random()
                    if roll < 0.04:
                        status, check_in, check_out, hours, late = (
                            AttendanceStatus.ABSENT, None, None, 0, 0
                        )
                    else:
                        start_minute = random.choice(
                            [0, 5, 10, 12, 15, 20, 25, 35, 45]  # some past the 15-min grace
                        )
                        late = max(start_minute - 15, 0)
                        check_in = datetime.combine(
                            day, time(9, 30), tzinfo=timezone.utc
                        ) + timedelta(minutes=start_minute)
                        hours = round(random.uniform(7.6, 9.4), 2)
                        check_out = check_in + timedelta(hours=hours)
                        if roll > 0.93:
                            status = AttendanceStatus.WFH
                        elif late > 0:
                            status = AttendanceStatus.LATE
                        else:
                            status = AttendanceStatus.PRESENT

                db.add(
                    Attendance(
                        company_id=employee.company_id,
                        employee_id=employee.id,
                        date=day,
                        check_in=check_in,
                        check_out=check_out,
                        working_hours=hours,
                        status=status,
                        is_late=late > 0,
                        late_minutes=late,
                    )
                )
                created += 1
        db.commit()
    return created


def _next_weekday(start: date, weeks_ahead: int) -> date:
    day = start + timedelta(days=weeks_ahead * 7)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def seed_leave(client, by_name: dict[str, int]):
    """A mix of approved, rejected and still-pending requests."""
    eli = login(client, "eli@nimbus.com")
    rohan = login(client, "rohan@nimbus.com")
    priya = login(client, "priya@nimbus.com")
    maya = login(client, "maya@nimbus.com")

    types = {b["leave_type_code"]: b["leave_type_id"] for b in eli.get(f"{API}/leaves/balances").json()}

    # Approved, in the past
    past = _next_weekday(TODAY - timedelta(days=30), 0)
    req = eli.post(
        f"{API}/leaves",
        json={
            "leave_type_id": types["CL"],
            "from_date": past.isoformat(),
            "to_date": (past + timedelta(days=1)).isoformat(),
            "reason": "Family wedding in Kochi",
        },
    ).json()
    maya.post(f"{API}/leaves/{req['id']}/approve", json={"comment": "Approved — enjoy!"})

    # Rejected
    clash = _next_weekday(TODAY, 2)
    req = rohan.post(
        f"{API}/leaves",
        json={
            "leave_type_id": types["CL"],
            "from_date": clash.isoformat(),
            "to_date": (clash + timedelta(days=2)).isoformat(),
            "reason": "Trip to Goa",
        },
    ).json()
    maya.post(
        f"{API}/leaves/{req['id']}/reject",
        json={"comment": "Release week — please reschedule to the following month"},
    )

    # Left PENDING on purpose, so approve/reject can be demoed live
    upcoming = _next_weekday(TODAY, 3)
    priya.post(
        f"{API}/leaves",
        json={
            "leave_type_id": types["SL"],
            "from_date": upcoming.isoformat(),
            "to_date": upcoming.isoformat(),
            "reason": "Doctor's appointment",
        },
    )
    later = _next_weekday(TODAY, 5)
    rohan.post(
        f"{API}/leaves",
        json={
            "leave_type_id": types["EL"],
            "from_date": later.isoformat(),
            "to_date": (later + timedelta(days=3)).isoformat(),
            "reason": "Annual family holiday",
        },
    )
    print("✓ Leave: 1 approved, 1 rejected, 2 left PENDING for the live demo")


def summary(today: date):
    last_month = today.replace(day=1) - timedelta(days=1)
    print(
        f"""
{'=' * 66}
  DEMO DATA READY — Nimbus Technologies
{'=' * 66}

  Password for every account below:  {PASSWORD}

    exec@nimbus.com     EXECUTIVE       Sovik Roy       (any company, via the top-bar picker)
    admin@nimbus.com    COMPANY_ADMIN   Ada Sharma      (everything in Nimbus)
    hana@nimbus.com     HR              Hana Kapoor     (people, payroll, reports)
    maya@nimbus.com     MANAGER         Maya Menon      (her team of 3 only)
    eli@nimbus.com      EMPLOYEE        Eli Fernandes   (own records only)

  Companies: Nimbus Technologies (full data) + Orbit Retail (empty)

  Left undone on purpose, so you can perform it on camera:
    * 2 leave requests are PENDING  -> approve/reject as maya@nimbus.com
    * payroll for {last_month.month:02d}/{last_month.year} is NOT run -> process it as admin
    * nobody has checked in today   -> check in/out as eli@nimbus.com
    * geofencing is OFF             -> switch on in Settings -> Attendance

  Start the server:   uvicorn app.main:app --reload
  Then open:          http://127.0.0.1:8000/docs
{'=' * 66}
"""
    )


if __name__ == "__main__":
    build()
