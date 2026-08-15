# HRMS Backend — MVP-1 (FastAPI)

Multi-tenant HR management API: authentication, company onboarding, employees,
attendance, leave, holidays, payroll, documents, notifications and reports.

## Stack

| Concern | Choice |
| --- | --- |
| Framework | FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 (sync) |
| Migrations | Alembic |
| Database | PostgreSQL (SQLite by default so it runs with zero setup) |
| Auth | JWT access + refresh tokens, bcrypt password hashing |
| Files | Local disk under `UPLOAD_DIR` |

Redis/Celery are **not** wired in MVP-1 — nothing in the current feature set needs a
queue. Notifications are in-app rows written in the same transaction as the event.

## Run it

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

copy .env.example .env          # cp on macOS/Linux
uvicorn app.main:app --reload
```

- API root: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json — feed this to `openapi-typescript`
  to generate frontend types.

On startup the app creates tables (when `AUTO_CREATE_TABLES=true`) and seeds the
global `roles` / `permissions` / `role_permissions` tables.

### PostgreSQL

```
DATABASE_URL=postgresql+psycopg2://hrms:hrms@localhost:5432/hrms
AUTO_CREATE_TABLES=false
```

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Tests

```bash
.venv\Scripts\python -m pytest -q
```

42 tests walk the full product flow — signup → company → onboarding wizard →
employees → attendance → leave → payroll → payslips — plus multi-tenant isolation
and per-role RBAC checks. They run against a throwaway SQLite file.

## Layout

```
app/
├── api/v1/          # HTTP layer: one router per module
├── core/            # config, database, security, RBAC, deps, pagination, seed
├── models/          # SQLAlchemy models (one file per domain)
├── schemas/         # Pydantic request/response models
├── services/        # business logic (auth, employee, attendance, leave, payroll, …)
└── utils/           # dates, file storage
```

Rule of thumb: routers validate and authorize, services decide, models persist.

## Multi-tenancy

Every business table carries `company_id`. The tenant is read from the authenticated
user (`Principal.tenant_id`) and **never** from request input — a client cannot ask
for another company's data by passing an id. Cross-tenant reads by id return `404`,
not `403`, so ids in other tenants are not discoverable.

## Roles and permissions

`SUPER_ADMIN`, `COMPANY_ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`.

Permissions live in [app/core/rbac.py](app/core/rbac.py) and are seeded into the
database. Routes declare what they need:

```python
ManageAccess = Perm(P.EMPLOYEE_CREATE)

@router.post("")
def create_employee(payload: EmployeeCreate, principal: ManageAccess): ...
```

Managers are additionally narrowed to their own reporting line at query time
(`Principal.team_employee_ids()`), so `GET /employees` returns different rows for
an HR user and a manager without either needing a different endpoint.

## Notable behaviour

- **Onboarding** advances a `companies.onboarding_step` state machine and never moves
  backwards, so a step can be re-submitted to edit it.
- **Company creation seeds defaults**: head-office location, a Mon–Fri 09:30–18:30 work
  policy, the four standard leave types (CL/SL/EL/LWP) and a salary structure
  (Basic 50% of CTC, HRA 40% of Basic, PF 12% of Basic, PT, ESI, TDS).
- **Leave day counting** skips weekly offs and holidays, so a Friday→Monday leave costs
  two days. Approving leave writes `LEAVE` attendance rows so payroll and reports agree.
- **Payroll** pulls salary + attendance, computes LOP (unpaid absences + unpaid leave +
  half-days), prorates components flagged `prorate_on_lop`, and moves through
  `DRAFT → PENDING_REVIEW → APPROVED → PAID`. Payslips can only be generated after
  approval and store an immutable JSON snapshot.
- **Timestamps** are UTC. Dates (`joining_date`, `from_date`, …) are plain `YYYY-MM-DD`.

## Deliberately out of scope for MVP-1

Google OAuth, biometric/geofenced attendance, statutory payroll filing, PDF payslip
rendering (the snapshot JSON has everything a renderer needs), email delivery, and
BI-style analytics.
