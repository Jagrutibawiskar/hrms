# Demo Recording Script — HRMS Backend MVP-1

Target length: **8–10 minutes**. Everything runs in Swagger UI at
http://127.0.0.1:8000/docs — no frontend needed.

## Before you hit record

```bash
cd backend
.venv\Scripts\python.exe scripts\seed_demo.py --reset     # fresh demo data
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs. Zoom the browser to ~125% so text is readable on video.

**How to log in inside Swagger:** run `POST /auth/login` → copy `access_token` from the
response → click the green **Authorize** button (top right) → paste → *Authorize* → *Close*.
You'll re-do this each time you switch persona. Password for everyone: `Password123!`

---

## Scene 1 — What was built (30s, no clicking)

Scroll slowly down the Swagger page so the tag list is visible.

> "This is the HRMS MVP-1 backend — FastAPI, PostgreSQL-ready, 120 endpoints across
> 13 modules: authentication, company onboarding, employees, attendance, leave,
> holidays, payroll, documents, notifications, reports and dashboards.
> It's multi-tenant and role-based, and it ships with 42 passing end-to-end tests."

---

## Scene 2 — Multi-tenancy & RBAC (90s) ← *lead with this, it's the differentiator*

Log in as **`admin@nimbus.com`**, then:

| Run | Point out |
| --- | --- |
| `GET /employees` | 9 employees — full roster |
| `GET /dashboard/hr` | headcount, present today, 2 pending leave requests |

Now **Authorize again as `maya@nimbus.com`** (MANAGER):

| Run | Point out |
| --- | --- |
| `GET /employees` | **only 4 rows** — Maya + her 3 reports |
| `GET /dashboard/hr` | **403 Forbidden** |

Now **`eli@nimbus.com`** (EMPLOYEE):

| Run | Point out |
| --- | --- |
| `GET /employees` | **1 row** — himself only |
| `GET /payroll/runs` | **403 Forbidden** |

> "Same endpoint, three roles, three different result sets. Scoping is enforced
> server-side, so the frontend can't bypass it. And the company is taken from the
> logged-in user's token — never from request input — so one company can never read
> another's data."

---

## Scene 3 — Attendance, live (60s)

Still as **`eli@nimbus.com`**:

1. `GET /attendance/today` → `checked_in: false`, `is_working_day: true`
2. `POST /attendance/check-in` with `{"is_wfh": false}` → note the timestamp and status
3. `GET /attendance/today` → now `checked_in: true`
4. `POST /attendance/check-out` with `{}` → **`working_hours` is computed automatically**
5. `POST /attendance/check-in` again → **`409` "You have already checked in today"**
6. `GET /attendance/me` → ~2 months of history
7. `GET /attendance/me/summary` → present / absent / late / WFH / leave counts

> "Status is derived from the work policy — under 4 hours is a half day, past the
> 15-minute grace period is marked late."

---

## Scene 4 — Leave with real balance math (2 min) ← *the strongest section*

As **`eli@nimbus.com`**:

1. `GET /leaves/balances` → Casual 12, Sick 6, Earned 15, and **used 2 from his approved leave**
2. `POST /leaves` — apply for a **Friday to Monday** leave:
   ```json
   { "leave_type_id": 1, "from_date": "<a Friday>", "to_date": "<the next Monday>",
     "reason": "Family function" }
   ```
   > **"Four calendar days, but the response says `days: 2` — weekends and holidays are
   > excluded automatically."**
3. `GET /leaves/balances` again → the 2 days moved into **`pending`**, `available` dropped
4. `POST /leaves` for the same dates again → **`409` overlapping request**
5. Try 30 days of Sick Leave → **`400` "Insufficient balance: requested 22 day(s), 4.0 available"**

Switch to **`maya@nimbus.com`** (the manager):

6. `GET /leaves/requests/pending` → her approval inbox, including Eli's new request
7. `POST /leaves/{id}/approve` with `{"comment": "Approved"}`
8. `GET /notifications` → **the manager was notified when it was applied**

Back as **`eli@nimbus.com`**:

9. `GET /leaves/balances` → the days moved from `pending` into `used`
10. `GET /notifications` → **"Leave approved"** notification

> "Balances, notifications and attendance all update in one transaction — approved
> leave writes LEAVE rows into attendance so payroll sees it too."

---

## Scene 5 — Payroll end to end (2.5 min) ← *the money shot*

Log in as **`admin@nimbus.com`**.

1. `GET /payroll/structures` → the default: Basic 50% of CTC, HRA 40% of Basic, PF, ESI, PT, TDS
2. `GET /payroll/structures/1/preview?ctc=1200000` →
   > "Type a CTC and the whole monthly breakup is computed — Basic ₹50,000,
   > HRA ₹20,000, PF ₹6,000. This is what the salary form calls as you type."
3. `POST /payroll/runs` with `{ "month": <last month>, "year": <year> }`
   Walk through one item in the response:
   - `working_days` vs `paid_days` vs **`lop_days`**
   - `earnings_breakdown` and `deductions_breakdown`
   - `net_pay = gross_earnings − total_deductions`
   > "It pulled each employee's salary structure, read their attendance for the month,
   > computed loss-of-pay from unpaid absences and half-days, and prorated every
   > component that should shrink with LOP."
4. `POST /payroll/runs/{id}/payslips` → **`400` — must be approved first**
5. `POST /payroll/runs/{id}/approve` → status becomes `APPROVED`
6. `POST /payroll/runs/{id}/payslips` → payslips generated
7. `POST /payroll/runs/{id}/mark-paid` → `PAID`

Switch to **`eli@nimbus.com`**:

8. `GET /payroll/payslips/me` → his payslips. Expand `snapshot`:
   > "Every payslip stores an immutable snapshot — employee, department, days worked,
   > every earning and deduction line. A salary revision next year can never change a
   > historical payslip."

---

## Scene 6 — Documents & access control (45s)

As **`admin@nimbus.com`**: `GET /documents/employee/3` → **2 documents** (offer letter +
an HR-only background check).

As **`eli@nimbus.com`**: `GET /documents/me` → **only 1** — the HR-only file is invisible.
Then `GET /documents/{hr_only_id}/download` → **`403`**.

---

## Scene 7 — Reports & CSV export (45s)

As **`admin@nimbus.com`**:

1. `GET /reports/attendance` → JSON with `columns` + `rows`
   > "One shape for all four reports, so the frontend has a single table component."
2. `GET /reports/payroll?export=true` → **downloads a CSV**, open it on screen
3. `GET /reports/headcount` → headcount per department

---

## Scene 8 — Close (30s)

Run the test suite on camera:

```bash
.venv\Scripts\python.exe -m pytest -q
```

> "42 tests, covering the whole flow plus tenant isolation and every role boundary."

Then show `FRONTEND_GUIDE.md`:

> "And the frontend team has a complete API guide — screen map, payloads, the RBAC
> matrix and a suggested build order. They can start today."

---

## If something goes wrong on camera

| Symptom | Fix |
| --- | --- |
| `401 Not authenticated` | Token expired (60 min). Re-run `POST /auth/login` and re-Authorize. |
| `403 not attached to a company` | You're using a token issued *before* the company existed. Log in again. |
| Data looks wrong / you want a clean take | `python scripts\seed_demo.py --reset` and restart the server. |
| Port 8000 busy | `uvicorn app.main:app --port 8001` |

## Reset between takes

```bash
.venv\Scripts\python.exe scripts\seed_demo.py --reset
```

Restores: 9 employees, 7 holidays, ~675 attendance records, 4 leave requests
(2 pending), one approved payroll with payslips, 2 documents.
