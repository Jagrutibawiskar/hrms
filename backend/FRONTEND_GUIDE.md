# HRMS — Frontend Developer Guide (MVP-1)

Everything a UI developer needs to build against this backend. Stack assumed:
Next.js (App Router) + TypeScript + Tailwind + shadcn/ui.

---

## 1. Start here

| | |
| --- | --- |
| Base URL | `http://127.0.0.1:8000` |
| API prefix | `/api/v1` |
| Swagger (live, try requests) | `http://127.0.0.1:8000/docs` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |

**Generate types instead of hand-writing them:**

```bash
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/types/api.d.ts
```

Re-run whenever the backend changes. Every request/response shape below is already
in that file — this guide explains *when* to call what.

---

## 2. Auth contract

JWT bearer tokens. Every request except signup/login/refresh/forgot/reset needs:

```
Authorization: Bearer <access_token>
```

### Token lifecycle

```
POST /api/v1/auth/signup   ──► { user, roles, tokens: { access_token, refresh_token, expires_in } }
POST /api/v1/auth/login    ──► same shape
POST /api/v1/auth/refresh  ──► { access_token, refresh_token, expires_in }   (body: { refresh_token })
GET  /api/v1/auth/me       ──► { user, roles, permissions[], company_id, is_onboarded, onboarding_step, employee_id }
```

- `access_token` lifetime: 60 min. `refresh_token`: 14 days.
- Store the access token in memory + refresh token in an httpOnly cookie (set by your
  Next.js route handler). Do **not** put tokens in `localStorage` for production.
- On any `401`, try refresh once; if that fails, redirect to `/login`.

### ⚠ The one gotcha: re-authenticate after creating a company

`POST /companies` attaches the user to a new company and grants `COMPANY_ADMIN`.
The **old access token still says `company_id: null`**. Immediately after a successful
company creation, call `POST /auth/refresh` (or re-login) and replace the token,
otherwise every following call returns `403 "This account is not attached to a company yet"`.

### `/auth/me` is your routing brain

Call it once after login and store the result. It drives everything:

```ts
if (!me.company_id)          router.push("/onboarding/company");
else if (!me.is_onboarded)   router.push(`/onboarding/${me.onboarding_step}`);
else                         router.push("/dashboard");
```

`me.permissions` is a flat string array (`"employee:read_all"`, `"payroll:process"`, …).
Gate nav items and buttons on it rather than on role names — that way adding a role
later doesn't break the UI.

---

## 3. Conventions

### Error shape

```jsonc
// 400 / 401 / 403 / 404 / 409
{ "detail": "Insufficient balance: requested 8 day(s), 4.0 available" }

// 422 validation
{ "detail": "Validation failed",
  "errors": [{ "field": "work_email", "message": "value is not a valid email address" }] }
```

`detail` is always safe to show to the user directly — the messages are written for humans.
Map `errors[].field` onto your form fields for inline validation.

| Code | Meaning in this API |
| --- | --- |
| `400` | Business rule broken (no balance, wrong payroll state, no check-in yet) |
| `401` | Missing/expired token → refresh or log out |
| `403` | Authenticated but not allowed → hide the control, don't just show an error |
| `404` | Not found **or** belongs to another company (deliberate — ids aren't discoverable) |
| `409` | Conflict (duplicate email, already checked in, overlapping leave) |

### Paginated list shape

`GET /employees`, `/attendance`, `/leaves/requests`, `/leaves/me`, `/notifications`, `/payroll/runs`:

```jsonc
{ "items": [...], "total": 87, "page": 1, "page_size": 25, "total_pages": 4 }
```

Query params: `?page=1&page_size=25` (max 200). Everything else returns a plain array.

### Dates & times

- Dates: `"2025-03-01"` (plain `YYYY-MM-DD`) — `joining_date`, `from_date`, `date`.
- Timestamps: UTC ISO-8601 — `check_in`, `applied_at`, `created_at`.
  **Convert to the user's local timezone in the UI.** The company timezone is on
  `GET /companies/current` → `timezone`.
- Times of day: `"09:30:00"` — work policy start/end/break.
- Weekdays: ISO numbers, **Monday = 1 … Sunday = 7**.

### File uploads

`multipart/form-data`. Max 10 MB. Allowed: PDF, PNG, JPEG, WEBP, DOC/DOCX, CSV, TXT.
Never set `Content-Type` manually — let the browser set the boundary.

---

## 4. Screen map

| Next.js route | Endpoints | Who sees it |
| --- | --- | --- |
| `/login` | `POST /auth/login` | public |
| `/signup` | `POST /auth/signup` | public |
| `/forgot-password` | `POST /auth/forgot-password` | public |
| `/reset-password` | `POST /auth/reset-password` | public |
| `/onboarding/company` | `POST /companies` | user with no company |
| `/onboarding/organization` | `POST /onboarding/organization` | COMPANY_ADMIN |
| `/onboarding/work-policy` | `POST /onboarding/work-policy` | COMPANY_ADMIN |
| `/onboarding/leave-policy` | `POST /onboarding/leave-policy` | COMPANY_ADMIN |
| `/onboarding/admin` | `POST /onboarding/admin` | COMPANY_ADMIN |
| `/onboarding/employees` | `POST /onboarding/employees` · `/import` · `/skip-employees` | COMPANY_ADMIN |
| `/dashboard` | `GET /dashboard/hr` **or** `GET /dashboard/me` | branch on `dashboard:hr` permission |
| `/employees` | `GET /employees` | ADMIN · HR · MANAGER (scoped) · EMPLOYEE (self only) |
| `/employees/[id]` | `GET /employees/{id}` + tab endpoints | same, scoped |
| `/attendance` | `GET /attendance` · `POST /attendance/check-in` `check-out` | all |
| `/attendance/reports` | `GET /reports/attendance` | ADMIN · HR |
| `/leaves` | `GET /leaves/me` · `GET /leaves/balances` · `POST /leaves` | all |
| `/leaves/requests` | `GET /leaves/requests` · `/requests/pending` · approve/reject | ADMIN · HR · MANAGER |
| `/holidays` | `GET /holidays` (+ manage for HR) | all |
| `/payroll` | `GET /payroll/runs` · `POST /payroll/runs` | ADMIN · HR |
| `/payroll/[id]` | `GET /payroll/runs/{id}` · approve · payslips | ADMIN · HR |
| `/payslips` | `GET /payroll/payslips/me` | all |
| `/documents` | `GET /documents/me` | all |
| `/reports` | `GET /reports/*` | ADMIN · HR |
| `/settings` | `GET/PATCH /companies/current` · `/organization/*` | ADMIN · HR |
| `/notifications` | `GET /notifications` | all |
| `/profile` | `GET /employees/me` · `POST /auth/change-password` | all |

---

## 5. Onboarding wizard — the one real sequence

`GET /onboarding/status` returns `{ current_step, is_onboarded, steps[] }`.
`current_step` is one of `company · organization · work_policy · leave_policy · admin · employees · completed`.
Use it to resume the wizard if the user reloads. Steps can be re-submitted to edit.

### Step 1 — Company · `POST /companies`

```jsonc
{
  "name": "Acme Corp", "industry": "Software",
  "company_size": "11-50",            // 1-10 | 11-50 | 51-200 | 201-500 | 501-1000 | 1000+
  "company_type": "Private Limited",
  "email": "hello@acme.com", "phone": "9876543210", "website": null,
  "country": "India", "state": "Karnataka", "city": "Bengaluru",
  "address": "1 MG Road", "postal_code": "560001",
  "timezone": "Asia/Kolkata", "currency": "INR", "fiscal_year_start_month": 4
}
```

→ `201`. **Now refresh the token** (see §2). The backend has already seeded a
head-office location, a Mon–Fri 09:30–18:30 work policy, four leave types and a
default salary structure — so show these as pre-filled defaults in the next steps.

### Step 2 — Organization · `POST /onboarding/organization`

```jsonc
{
  "departments":  [{ "name": "Engineering" }, { "name": "People Ops" }],
  "designations": [{ "name": "Software Engineer", "department_id": null, "level": 3 }],
  "locations":    [{ "name": "Bengaluru Office", "city": "Bengaluru", "is_headquarters": true }]
}
```

Duplicates by name are silently skipped, so re-submitting is safe. Response
`created` tells you how many of each were actually added.

### Step 3 — Work policy · `POST /onboarding/work-policy`

```jsonc
{
  "working_days": [1,2,3,4,5],        // Mon=1 … Sun=7
  "start_time": "09:30:00", "end_time": "18:30:00",
  "break_start": "13:00:00", "break_end": "14:00:00",
  "full_day_hours": 8, "half_day_hours": 4, "late_grace_minutes": 15
}
```

UI: a 7-toggle weekday row + two time pickers. Weekly-off is *derived* — read
`weekly_off_days` back from the response rather than asking for it.

### Step 4 — Leave policy · `POST /onboarding/leave-policy`

Send `{"leave_types": []}` to accept the seeded defaults (CL 12, SL 6, EL 15, LWP 0),
or send the full array to override. Matching is by `code`, so sending an existing
code updates it instead of creating a duplicate.

```jsonc
{ "leave_types": [
  { "name": "Casual Leave", "code": "CL", "annual_quota": 12, "is_paid": true,
    "requires_approval": true, "allow_half_day": true,
    "carry_forward": false, "max_carry_forward": 0, "requires_attachment": false }
]}
```

### Step 5 — Admin profile · `POST /onboarding/admin`

```jsonc
{ "first_name": "Ada", "last_name": "Admin", "phone": "9000000000",
  "designation_id": null, "designation_name": "Founder",   // name auto-creates the designation
  "department_id": null, "location_id": null, "joining_date": "2024-01-01" }
```

This also creates the admin's own **employee record**, so they appear in the roster.

### Step 6 — Employees · three options

| Option | Endpoint |
| --- | --- |
| Add manually | `POST /onboarding/employees` — body is an **array** of employee objects |
| Import CSV | `POST /onboarding/employees/import` (multipart `file`) |
| Skip | `POST /onboarding/skip-employees` |

Any of the three finishes onboarding (`is_onboarded: true`). Download the CSV
template from `GET /employees/csv-template`.

**CSV columns:** `employee_code, first_name, last_name, work_email, department,
designation, location, manager_email, joining_date, employment_type, phone,
date_of_birth, gender`

Import is row-by-row — good rows commit, bad rows are reported:

```jsonc
{ "created": 12, "failed": 2, "created_employee_ids": [5,6,...],
  "errors": [{ "row": 4, "error": "Department 'Sales' not found in this company" }] }
```

Show this as a result table with the row numbers so the user can fix their file.

---

## 6. Endpoints by module

Legend for **Access**: `A` = COMPANY_ADMIN, `H` = HR, `M` = MANAGER (own team only), `E` = EMPLOYEE (own records only).

### Auth

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| POST | `/auth/signup` | public | password min 8 chars |
| POST | `/auth/login` | public | |
| POST | `/auth/refresh` | public | body `{ refresh_token }` |
| POST | `/auth/logout` | all | stateless — also clear client tokens |
| GET | `/auth/me` | all | **routing brain**, see §2 |
| POST | `/auth/forgot-password` | public | always 200 (no email enumeration); in DEBUG the token is echoed in the message |
| POST | `/auth/reset-password` | public | `{ token, new_password }`, 1-hour expiry |
| POST | `/auth/change-password` | all | `{ current_password, new_password }` |
| POST | `/auth/verify-email` | public | `{ token }` |

### Company & settings

| Method | Path | Access |
| --- | --- | --- |
| POST | `/companies` | any user without a company |
| GET | `/companies/current` | A H M E |
| PATCH | `/companies/current` | A |

### Organization (Settings screens)

| Method | Path | Access |
| --- | --- | --- |
| GET | `/organization/departments` · `/designations` · `/locations` · `/leave-types` · `/work-policies` | A H M E |
| POST | `/organization/departments` · `/designations` · `/locations` · `/leave-types` | A H |
| PATCH | `/organization/{resource}/{id}` | A H |
| DELETE | `/organization/departments/{id}` · `/designations/{id}` · `/locations/{id}` | A H |
| PUT | `/organization/work-policies/default` | A H |

`DELETE` is soft when the record is in use — it returns
`"Department has 12 employee(s); deactivated instead"` with `200`. Surface that message;
don't assume the row disappeared. Add `?include_inactive=true` to list deactivated rows.

### Employees

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| GET | `/employees` | A H M E | paginated; filters below |
| POST | `/employees` | A H | returns `{ employee, generated_password }` |
| GET | `/employees/me` | all | current user's own record |
| GET | `/employees/{id}` | A H · M(team) · E(self) | full profile with `personal` + `employment` |
| PATCH | `/employees/{id}` | A H | partial; nest `employment` / `personal` |
| POST | `/employees/{id}/deactivate` | A H | blocked if they still manage people |
| POST | `/employees/{id}/activate` | A H | |
| GET | `/employees/{id}/team` | A H M | direct reports |
| DELETE | `/employees/{id}` | A H | only when no attendance/leave/payroll history |
| GET | `/employees/csv-template` | A H | CSV download |
| POST | `/employees/import` | A H | multipart `file` |

**List filters:** `?search=` (name/code/email) `&department_id=` `&designation_id=`
`&location_id=` `&manager_id=` `&status=` `&page=` `&page_size=`

**Create body** — note `employment` is required and nested:

```jsonc
{
  "first_name": "Eli", "last_name": "Engineer", "work_email": "eli@acme.com",
  "employee_code": null,               // null → auto EMP0001, EMP0002, …
  "employment": {
    "department_id": 1, "designation_id": 2, "location_id": 1,
    "manager_id": 4, "joining_date": "2025-03-01",
    "employment_type": "FULL_TIME", "is_manager": false, "probation_months": 3
  },
  "personal": { "date_of_birth": "1996-05-20", "gender": "OTHER", "phone": "98765..." },
  "create_login": true,                // false → record only, no account
  "password": null,                    // null → auto-generated, returned once
  "role": "EMPLOYEE"                   // EMPLOYEE | MANAGER | HR | COMPANY_ADMIN
}
```

`generated_password` is returned **once** and never again — show it in a
copy-to-clipboard dialog before the user navigates away.

**Employee profile tabs** map to:

| Tab | Endpoint |
| --- | --- |
| Overview / Personal / Employment | `GET /employees/{id}` |
| Attendance | `GET /attendance?employee_id={id}` + `GET /attendance/summary/{id}` |
| Leave | `GET /leaves/requests?employee_id={id}` + `GET /leaves/balances/{id}` |
| Documents | `GET /documents/employee/{id}` |
| Salary | `GET /payroll/salaries/{id}` |

### Attendance

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| GET | `/attendance/today` | all | **drives the check-in widget** |
| POST | `/attendance/check-in` | all | `{ is_wfh, remarks }` → `409` if already in |
| POST | `/attendance/check-out` | all | `400` if never checked in, `409` if already out |
| GET | `/attendance/me` | all | `?from_date=&to_date=` (defaults to this month) |
| GET | `/attendance/me/summary` | all | counts + total/average hours |
| GET | `/attendance` | A H · M(team) | paginated, `?employee_id=&department_id=&status=&from_date=&to_date=` |
| GET | `/attendance/summary/{employee_id}` | A H M | |
| PUT | `/attendance/{employee_id}/{date}` | A H | regularize a missed punch |
| POST | `/attendance/backfill` | A H | marks a past day's missing rows ABSENT/WEEKEND/HOLIDAY |

**Check-in widget state machine** — read it straight off `/attendance/today`:

```jsonc
{ "date": "2026-08-13", "server_time": "2026-08-13T04:02:11Z",
  "checked_in": false, "checked_out": false,
  "check_in": null, "check_out": null, "working_hours": 0, "status": null,
  "is_working_day": true, "is_holiday": false, "holiday_name": null, "on_leave": false }
```

| Condition | Show |
| --- | --- |
| `on_leave` | "You're on leave today" — no buttons |
| `is_holiday` | holiday name — allow optional check-in |
| `!is_working_day` | "Weekly off" — allow optional check-in |
| `!checked_in` | **CHECK IN** button |
| `checked_in && !checked_out` | "Working" + live timer from `check_in` + **CHECK OUT** |
| `checked_out` | summary with `working_hours` |

Use `server_time` to seed the timer so the widget doesn't drift with a wrong client clock.

**Statuses:** `PRESENT · ABSENT · HALF_DAY · LATE · LEAVE · HOLIDAY · WFH · WEEKEND`
— give each a distinct chip colour; they're used in tables, reports and the payslip.

### Leave

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| GET | `/leaves/balances` | all | own balances — the balance cards |
| GET | `/leaves/me` | all | own requests, paginated, `?status=` |
| POST | `/leaves` | all | apply |
| POST | `/leaves/with-attachment` | all | multipart version, for types that require a document |
| POST | `/leaves/{id}/cancel` | all | own request only |
| GET | `/leaves/requests` | A H · M(team) | `?status=&employee_id=&department_id=&from_date=&to_date=` |
| GET | `/leaves/requests/pending` | A H M | **the approval inbox** |
| GET | `/leaves/{id}` | A H M E | |
| POST | `/leaves/{id}/approve` | A H M | `{ comment }` optional |
| POST | `/leaves/{id}/reject` | A H M | `{ comment }` **required** |
| GET | `/leaves/balances/{employee_id}` | A H M | |
| PUT | `/leaves/balances` | A H | HR override of an allocation |

**Balance card data:**

```jsonc
{ "leave_type_id": 1, "leave_type_name": "Casual Leave", "leave_type_code": "CL",
  "is_paid": true, "year": 2026,
  "allocated": 12, "carried_forward": 0, "used": 4, "pending": 2,
  "available": 6, "total": 12 }
```

Render as `used / total` with a progress bar; `pending` is reserved-but-not-approved,
so show it as a lighter segment. **`available = total − used − pending`.**

**Apply body:**

```jsonc
{ "leave_type_id": 1, "from_date": "2026-09-07", "to_date": "2026-09-08",
  "is_half_day": false, "half_day_session": null,   // FIRST_HALF | SECOND_HALF
  "reason": "Family function", "contact_during_leave": "9876543210" }
```

Rules the UI should enforce *before* submitting, to avoid avoidable errors:

- Half-day ⇒ `from_date === to_date` and `half_day_session` required.
- `to_date >= from_date`.
- **Day count excludes weekly offs and holidays** — Fri→Mon costs 2 days, not 4.
  Compute your preview from `/organization/work-policies` + `/holidays` so the number
  you show matches the `days` the server returns.
- Overlapping an existing pending/approved request → `409`.
- Exceeding balance on a *paid* type → `400`. Unpaid (`LWP`) has no cap.

Approval flow: employee applies → notification to their **manager** (or to HR if they
have no manager) → approve/reject → notification back to the employee → balance moves
from `pending` to `used` (approve) or is released (reject).

### Holidays

| Method | Path | Access |
| --- | --- | --- |
| GET | `/holidays?year=2026&location_id=` | all |
| GET | `/holidays/upcoming?limit=5` | all (auto-filtered to the caller's location) |
| POST | `/holidays` · `/holidays/bulk` | A H |
| PATCH · DELETE | `/holidays/{id}` | A H |

`location_id: null` on a holiday means company-wide. Use `/bulk` to load a whole
year's calendar in one call — existing entries are skipped.

### Payroll

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| GET | `/payroll/components` | A H | Basic, HRA, PF, PT … |
| POST · PATCH | `/payroll/components` · `/{id}` | A H | |
| GET · POST | `/payroll/structures` | A H | |
| GET | `/payroll/structures/{id}/preview?ctc=1200000` | A H | **live CTC breakup preview** |
| GET · POST | `/payroll/salaries/{employee_id}` | A H | history / assign |
| GET | `/payroll/salaries/me/current` | all | own salary |
| GET · POST | `/payroll/runs` | A H | list / process |
| GET | `/payroll/runs/{id}` | A H | run + all line items |
| POST | `/payroll/runs/{id}/approve` | A | |
| POST | `/payroll/runs/{id}/payslips` | A H | generate (approved runs only) |
| GET | `/payroll/runs/{id}/payslips` | A H | |
| POST | `/payroll/runs/{id}/mark-paid` | A | |
| DELETE | `/payroll/runs/{id}` | A H | draft/pending only |
| GET | `/payroll/payslips/me` | all | **My Payslips** |
| GET | `/payroll/payslips/{id}` | owner or A H | |

**State machine — drive your buttons off `status`:**

```
DRAFT ──process──► PENDING_REVIEW ──approve──► APPROVED ──mark-paid──► PAID
                                                   │
                                                   └──► generate payslips
```

Payslips **cannot** be generated before `APPROVED` (returns `400`). Approved/paid runs
cannot be deleted.

**Salary assignment** — use the preview endpoint as the user types the CTC:

```jsonc
// GET /payroll/structures/1/preview?ctc=1200000
[ { "code": "BASIC",  "name": "Basic",  "component_type": "EARNING",   "monthly_amount": 50000 },
  { "code": "HRA",    "name": "HRA",    "component_type": "EARNING",   "monthly_amount": 20000 },
  { "code": "PF",     "name": "PF",     "component_type": "DEDUCTION", "monthly_amount": 6000 },
  { "code": "PT",     "name": "PT",     "component_type": "DEDUCTION", "monthly_amount": 200 } ]
```

Then `POST /payroll/salaries/{employee_id}` with
`{ structure_id, ctc, effective_from, payment_mode, bank_account_number, bank_ifsc }`.
Leave `components: []` to let the server derive the amounts. `effective_from` must be
**after** the current structure's start date — the previous record is closed, not deleted.

**Processing:** `POST /payroll/runs` with `{ month, year, employee_ids?: number[], notes? }`.
Response includes every line item:

```jsonc
{ "id": 3, "month": 7, "year": 2026, "status": "PENDING_REVIEW",
  "employee_count": 24, "total_gross": 1840000, "total_deductions": 210400, "total_net": 1629600,
  "items": [{
     "employee_id": 3, "employee_code": "EMP0003", "employee_name": "Eli Engineer",
     "working_days": 23, "paid_days": 21, "lop_days": 2,
     "gross_earnings": 84782.61, "total_deductions": 6200, "net_pay": 78582.61,
     "earnings_breakdown":   [{ "code": "BASIC", "name": "Basic", "amount": 45652.17 }],
     "deductions_breakdown": [{ "code": "PF", "name": "Provident Fund", "amount": 6000 }]
  }]}
```

Employees without a salary structure, or who joined after the period, are skipped and
listed in `notes` — surface that as a warning banner so HR knows who was left out.

**Payslip** carries an immutable `snapshot` object with employee details, days,
earnings, deductions and totals — render the payslip entirely from `snapshot` so a
later salary revision never changes a historical payslip. There is no PDF endpoint in
MVP-1; render to HTML and use the browser's print-to-PDF.

### Documents

| Method | Path | Access |
| --- | --- | --- |
| GET | `/documents/me` | all — own visible documents |
| GET | `/documents/employee/{id}` | A H (all) · E (own, visible only) |
| POST | `/documents` | A H — multipart |
| GET | `/documents/{id}/download` | owner (if visible) or A H |
| PATCH · DELETE | `/documents/{id}` | A H |

Upload fields: `employee_id`, `title`, `document_type`, `description`,
`is_visible_to_employee`, `file`.

`is_visible_to_employee: false` = HR-internal; the employee cannot see or download it.
Make that toggle explicit and clearly labelled in the upload dialog.

Download returns a binary stream — use a blob + object URL, or a plain
`<a href>` with the token in a proxied Next.js route handler.

### Notifications

| Method | Path | Access |
| --- | --- | --- |
| GET | `/notifications?unread_only=true` | all, paginated |
| GET | `/notifications/count` | all → `{ unread, total }` |
| POST | `/notifications/read` | all — `{}` marks all read, `{ notification_ids: [...] }` marks some |
| DELETE | `/notifications/{id}` | all |

Poll `/notifications/count` every ~60s for the bell badge (no websockets in MVP-1).
Each row carries `action_url` (e.g. `/leaves/requests/12`) — make the item clickable.

Events: `LEAVE_APPLIED · LEAVE_APPROVED · LEAVE_REJECTED · LEAVE_CANCELLED ·
PAYROLL_PROCESSED · PAYSLIP_GENERATED · EMPLOYEE_ADDED · DOCUMENT_UPLOADED ·
ATTENDANCE_REGULARIZED` — give each an icon.

### Dashboards

**`GET /dashboard/hr`** (needs `dashboard:hr`):

```jsonc
{ "counts": { "total_employees": 48, "active_employees": 46, "present_today": 41,
              "absent_today": 2, "on_leave_today": 3, "late_today": 5, "wfh_today": 4 },
  "pending": { "pending_leave_requests": 7, "pending_payroll_runs": 1 },
  "new_joiners": [...], "upcoming_birthdays": [...], "upcoming_holidays": [...],
  "recent_leave_requests": [...] }
```

**`GET /dashboard/me`** (everyone): `today` (same shape as `/attendance/today`),
`leave_balances`, `pending_leaves`, `upcoming_holidays`, `unread_notifications`,
`attendance_this_month`.

Render one or the other based on `me.permissions.includes("dashboard:hr")`.

### Reports

| Path | Filters |
| --- | --- |
| `GET /reports/employees` | `department_id`, `status` |
| `GET /reports/attendance` | `from_date`, `to_date`, `department_id`, `employee_id` |
| `GET /reports/leaves` | `from_date`, `to_date`, `department_id`, `employee_id`, `status` |
| `GET /reports/payroll` | `year`, `month`, `department_id` |
| `GET /reports/headcount` | — (headcount by department; good for a bar chart) |

All four main reports take **`&export=true`** to return a CSV download instead of JSON.
JSON shape is `{ columns: string[], rows: object[], count: number }` — you can drive a
generic table component off `columns` and reuse it for all four.

---

## 7. RBAC — what each role sees

| Nav item | COMPANY_ADMIN | HR | MANAGER | EMPLOYEE |
| --- | :-: | :-: | :-: | :-: |
| Dashboard (HR view) | ✅ | ✅ | — | — |
| Dashboard (my view) | ✅ | ✅ | ✅ | ✅ |
| Employees | all | all | own team | self only |
| Add / edit employee | ✅ | ✅ | — | — |
| Attendance (others) | all | all | own team | — |
| Regularize attendance | ✅ | ✅ | — | — |
| Leave requests (others) | all | all | own team | — |
| Approve / reject leave | ✅ | ✅ | own team | — |
| Holidays — view | ✅ | ✅ | ✅ | ✅ |
| Holidays — manage | ✅ | ✅ | — | — |
| Payroll | ✅ | ✅ | — | — |
| Approve payroll | ✅ | — | — | — |
| My payslips | ✅ | ✅ | ✅ | ✅ |
| Documents — manage | ✅ | ✅ | — | — |
| Reports | ✅ | ✅ | — | — |
| Settings | ✅ | ✅ | — | — |

**Implementation note:** the same endpoint returns different rows per role — a manager
calling `GET /employees` gets only their reports, an employee gets only themselves.
You do not need separate "my team" screens; build one screen and let the API scope it.

Gate the UI on permissions from `/auth/me`:

```ts
const can = (p: string) => me.permissions.includes(p);

can("employee:create")   // show "Add Employee"
can("leave:approve")     // show the approval inbox
can("payroll:process")   // show Payroll nav
can("payroll:approve")   // show the Approve button
can("dashboard:hr")      // HR dashboard vs employee dashboard
can("report:view")       // show Reports nav
can("organization:manage")// show Settings nav
```

Server-side checks are enforced regardless — client gating is for UX, not security.

---

## 8. Enum reference (dropdown values)

| Field | Values |
| --- | --- |
| `company_size` | `1-10` `11-50` `51-200` `201-500` `501-1000` `1000+` |
| `role` | `SUPER_ADMIN` `COMPANY_ADMIN` `HR` `MANAGER` `EMPLOYEE` |
| `employment_type` | `FULL_TIME` `PART_TIME` `CONTRACT` `INTERN` `CONSULTANT` |
| `status` (employee) | `ACTIVE` `PROBATION` `NOTICE_PERIOD` `INACTIVE` `TERMINATED` `RESIGNED` |
| `gender` | `MALE` `FEMALE` `OTHER` `UNDISCLOSED` |
| `marital_status` | `SINGLE` `MARRIED` `DIVORCED` `WIDOWED` `OTHER` |
| `status` (attendance) | `PRESENT` `ABSENT` `HALF_DAY` `LATE` `LEAVE` `HOLIDAY` `WFH` `WEEKEND` |
| `status` (leave) | `PENDING` `APPROVED` `REJECTED` `CANCELLED` |
| `half_day_session` | `FIRST_HALF` `SECOND_HALF` |
| `holiday_type` | `PUBLIC` `OPTIONAL` `RESTRICTED` `COMPANY` |
| `document_type` | `AADHAAR` `PAN` `OFFER_LETTER` `JOINING_LETTER` `EXPERIENCE_LETTER` `EDUCATION` `OTHER` |
| `component_type` | `EARNING` `DEDUCTION` |
| `calculation_type` | `FIXED` `PERCENT_OF_BASIC` `PERCENT_OF_CTC` `PERCENT_OF_GROSS` |
| `status` (payroll) | `DRAFT` `PENDING_REVIEW` `APPROVED` `PAID` `CANCELLED` |
| `onboarding_step` | `company` `organization` `work_policy` `leave_policy` `admin` `employees` `completed` |

---

## 9. Suggested build order

1. **API client + auth** — fetch wrapper with token injection, 401→refresh→retry,
   `/auth/me` bootstrap, route guards. Everything else depends on this.
2. **Login / signup / forgot-password.**
3. **Onboarding wizard** — six steps, resume from `current_step`. Ship this before the
   app shell; nothing else is reachable until a company exists.
4. **App shell** — sidebar driven by `me.permissions`, notification bell, user menu.
5. **Employees** — list + profile tabs. Biggest surface, unlocks everything else.
6. **Attendance widget + attendance table.** Small, high-visibility, quick win.
7. **Leave** — balances, apply form, approval inbox. The most business logic; budget time
   for the day-count preview.
8. **Payroll** — salary assignment with live preview, then the run → approve → payslip flow.
9. **Documents, notifications, holidays, reports** — mostly CRUD over patterns you'll
   already have.

### Reusable components worth building once

`<StatusChip status type>` · `<DataTable>` (paginated, filterable, drives every list and
report) · `<EmptyState>` · `<PermissionGate permission>` · `<DateRangePicker>` ·
`<EmployeePicker>` · `<ConfirmDialog>` · `<FileUpload>` · `<CurrencyValue>` (respects
`company.currency`).

---

## 10. Quick smoke test

```bash
# 1. Sign up
curl -X POST http://127.0.0.1:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"Password123!","first_name":"Ada"}'

# 2. Create company (use the access_token from step 1)
curl -X POST http://127.0.0.1:8000/api/v1/companies \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"name":"Acme","industry":"Software","company_size":"11-50","email":"hi@acme.com",
       "phone":"9876543210","country":"India","state":"KA","city":"Bengaluru",
       "address":"1 MG Road","postal_code":"560001"}'

# 3. Refresh the token, then GET /auth/me — company_id is now set.
```

Or just open **`/docs`**, click *Authorize*, paste the token and click through every
endpoint. That is the fastest way to see real response shapes.

---

**Note on test emails:** the `.test`, `.invalid` and `.localhost` TLDs are rejected by
email validation (they're reserved by RFC 2606). Use `.com`, `.co`, `.io` etc. in seed
and test data.
