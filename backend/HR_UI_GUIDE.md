# HR Module — UI Build Guide (MVP-2)

What to build on top of the HR backend. Every screen below maps to endpoints that
exist and are tested — nothing here is aspirational.

Base URL `http://127.0.0.1:8000/api/v1` · Swagger `/docs` (**HR** tag) ·
Auth and conventions: see [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md).

---

## 1. HR Dashboard

`GET /hr/overview`

```jsonc
{
  "counts": {
    "total_employees": 124, "active": 118, "draft_profiles": 6,
    "pending_documents": 12, "rejected_documents": 2
  },
  "documents": { "total": 856, "verified": 720, "pending": 104, "rejected": 22, "expired": 10 },
  "upcoming_joiners": [ { "id": 7, "employee_code": "EMP-0007", "full_name": "Rahul Sharma",
                          "designation": "Software Engineer", "joining_date": "2026-09-01",
                          "profile_status": "DRAFT" } ],
  "recent_employees": [ /* same shape */ ]
}
```

**Layout**

```
Total Employees   Active   Draft Profiles   Pending Documents   Rejected
     124           118           6                 12               2

┌ Upcoming Joining ─────────────┐  ┌ Recent Employees ────────────┐
│ Rahul Sharma  EMP-0007        │  │ …                            │
│ Software Engineer · 1 Sep     │  │                              │
│ [DRAFT]                       │  │                              │
└───────────────────────────────┘  └──────────────────────────────┘

Quick actions:  [ + Add Employee ]  [ Import CSV ]  [ Document Verification ]
```

- **Draft Profiles** and **Pending Documents** are the two numbers HR acts on — make them clickable, filtering the relevant list.
- Show a `DRAFT` chip on any joiner whose `profile_status` is `DRAFT`.

---

## 2. Employee List

`GET /employees?search=&department_id=&designation_id=&location_id=&manager_id=&status=&page=&page_size=`

Returns `{ items, total, page, page_size, total_pages }`.

| Column | Field |
|---|---|
| Employee ID | `employee_code` |
| Name | `full_name` + `work_email` underneath |
| Department | `department_name` |
| Designation | `designation_name` |
| Joining Date | `joining_date` |
| Manager | `manager_name` |
| Location | `location_name` |
| Status | `status` chip |
| Documents | see below |
| Actions | View |

**Documents column** — the list endpoint doesn't carry document counts (it would
mean N queries). Two options, pick one:

1. **Lazy per row** — call `GET /hr/employees/{id}/documents/checklist` when the row
   scrolls into view; render `required_verified / required_total`.
2. **Skip in the list** — show it on the profile only. Simpler, and honestly enough.

Header actions: `[ + Add Employee ]` `[ Import CSV ]`

---

## 3. Add Employee — 6-step wizard

The backend saves **each step independently**, so build it as a real wizard with a
persistent draft, not one giant form. HR can leave and come back.

```
POST /hr/employees/draft
  { first_name, middle_name?, last_name?, work_email, employee_code?, joining_date? }
  → { employee_id, employee_code, profile_status: "DRAFT", next_step: "personal" }
```

Call this on **Next** from step 1. Everything after uses `employee_id`.

### Progress bar

```
①Personal ─ ②Contact ─ ③Employment ─ ④Documents ─ ⑤Bank & Statutory ─ ⑥Review
```

Allow jumping back to any completed step. Never block forward movement except at Review.

### Step 1 — Personal · `PATCH /hr/employees/{id}/personal`

```jsonc
{ "first_name": "Rahul", "middle_name": "Kumar", "last_name": "Sharma",
  "date_of_birth": "1996-04-12", "gender": "MALE",
  "blood_group": "O+", "nationality": "Indian", "marital_status": "SINGLE" }
```

Required in UI: first name. Others optional — the backend won't reject them, and
Review will flag what's missing.

`gender`: `MALE · FEMALE · OTHER · UNDISCLOSED`
`marital_status`: `SINGLE · MARRIED · DIVORCED · WIDOWED · OTHER`

### Step 2 — Contact · `PATCH /hr/employees/{id}/contact`

```jsonc
{ "personal_email": "rahul@example.com", "phone": "9876543210",
  "alternate_phone": "9812345678",
  "address_line1": "", "address_line2": "", "city": "Mumbai",
  "state": "", "country": "", "postal_code": "",
  "emergency_contact_name": "Sunita Sharma",
  "emergency_contact_relation": "Mother",
  "emergency_contact_phone": "9800000000" }
```

Group emergency contact in its own bordered block — it reads as a separate concern.

### Step 3 — Employment · `PATCH /hr/employees/{id}/employment`

```jsonc
{ "employee_code": "EMP-0007",        // optional override
  "joining_date": "2026-09-01",       // the one genuinely required field
  "employment_type": "FULL_TIME",
  "work_mode": "HYBRID",
  "department_id": 1, "designation_id": 2, "location_id": 1,
  "manager_id": 4, "work_policy_id": null,
  "probation_months": 3, "confirmation_date": null,
  "is_manager": false, "status": "ACTIVE" }
```

- **Employee code**: prefill from `GET /hr/employee-code/preview?count=1`, shown
  read-only with an "Edit" link. Don't make HR type it.
- Dropdowns from `/organization/departments`, `/designations`, `/locations`
- Manager from `/employees?page_size=200`
- `employment_type`: `FULL_TIME · PART_TIME · CONTRACT · INTERN · CONSULTANT`
- `work_mode`: `OFFICE · REMOTE · HYBRID`
- `status`: `ACTIVE · PROBATION · NOTICE_PERIOD · INACTIVE · TERMINATED · RESIGNED`

Saving this step also creates the employee's leave balances.

### Step 4 — Documents

Drive the whole step from the checklist:

```
GET /hr/employees/{id}/documents/checklist
```

```jsonc
{ "employee_id": 7, "required_total": 6, "required_verified": 2, "complete": false,
  "rows": [
    { "document_type": "RESUME", "is_required": true, "document_id": 31,
      "file_name": "rahul_cv.pdf", "status": "VERIFIED", "expiry_date": null,
      "uploaded_at": "...", "rejection_reason": null, "missing": false },
    { "document_type": "PAN", "is_required": true, "document_id": null,
      "status": null, "missing": true }
  ] }
```

Render one row per `rows` entry — **the policy decides the rows, not the UI**:

```
Document Type      Upload            Status      Expiry      Actions
Resume *           rahul_cv.pdf      ✓ Verified  —           [View] [Replace]
PAN *              —                 Required    —           [Upload]
Aadhaar *          aadhaar.pdf       ⏳ Pending   —           [View] [Replace]
Offer Letter *     offer.pdf         ✗ Rejected  —           [Re-upload]
                   ↳ "Document is not readable."
Work Permit        permit.pdf        ⚠ Expired   12 Mar 2026 [Replace]
```

`*` = `is_required`. Show `rejection_reason` inline under a rejected row — that's the
only way the employee knows what to fix.

**Upload** — `POST /documents` (multipart):

```
employee_id, title, document_type, description?, is_visible_to_employee, expiry_date?, file
```

Everything uploads as `PENDING`. Max 10 MB. PDF, image, DOC/DOCX, CSV, TXT.

**Resume** gets its own emphasised card at the top of this step — it's the one
document that will be AI-parsed in MVP-3, so treat it as first-class:

```
┌ Resume / CV ─────────────────────────┐
│  [ Upload Resume ]                   │
│  PDF, DOC, DOCX · max 5 MB           │
└──────────────────────────────────────┘
```

Header shows progress: **`4 / 6 required documents verified`**

### Step 5 — Bank & Statutory

**Bank** · `PUT /hr/employees/{id}/bank` — needs `salary:read` permission

```jsonc
{ "bank_name": "HDFC Bank", "account_holder_name": "Rahul Sharma",
  "account_number": "50100123454521", "ifsc": "HDFC0001234", "branch": "Andheri" }
```

Response returns both `account_number` (only if you're allowed) and
`account_number_masked` (`XXXX XXXX 4521`).

**Show the masked value everywhere except this form.** `GET .../bank` returns 404 for
anyone without `salary:read` — hide the whole section for them rather than showing an error.

**Statutory** · `PUT /hr/employees/{id}/statutory`

```jsonc
{ "pan": "ABCDE1234F",
  "pf_eligible": true,  "uan": "100200300400", "pf_number": "",
  "esi_eligible": false, "esi_number": "",
  "professional_tax_state": "Karnataka" }
```

Build this as **conditional fields**, matching the backend:

```
PAN                        [____________]

Eligible for PF?           ( ) Yes  (•) No
   ↳ if Yes:  UAN          [____________]
              PF Number    [____________]

Eligible for ESI?          ( ) Yes  (•) No
   ↳ if Yes:  ESI Number   [____________]
```

Turning eligibility **off clears the numbers server-side** — reflect that in the UI so
it doesn't look like data was lost by accident.

### Step 6 — Review · `GET /hr/employees/{id}/review`

```jsonc
{ "employee_id": 7, "employee_code": "EMP-0007", "full_name": "Rahul Sharma",
  "profile_status": "DRAFT",
  "can_complete": false,
  "blocking": ["Joining Letter is missing", "Pan is pending"],
  "sections": [
    { "name": "Personal", "complete": true,
      "items": [ { "label": "Name", "ok": true, "detail": "Rahul Sharma" } ] }
  ] }
```

Render each `section` as a card, each `item` with ✓ / ⚠. Then:

```
⚠ This employee cannot be completed yet:
   • Joining Letter is missing
   • Pan is pending

[ Save as Draft ]        [ Complete Employee ]
                          ↑ disabled while can_complete is false
```

- **Save as Draft** = just navigate away. It's already saved.
- **Complete Employee** → `POST /hr/employees/{id}/complete`
- Admins additionally get `[ Complete anyway ]` → `?force=true`. Only show this if
  `permissions` includes `settings:manage`; a non-admin gets a 400.

---

## 4. Employee Profile

Tabs: **Overview · Personal · Employment · Documents · Attendance · Leave · Payroll · Bank & Statutory · Activity**

| Tab | Endpoint |
|---|---|
| Overview / Personal / Employment | `GET /employees/{id}` |
| Documents | `GET /hr/employees/{id}/documents/checklist` |
| Attendance | `GET /attendance?employee_id={id}` + `/attendance/summary/{id}` |
| Leave | `GET /leaves/requests?employee_id={id}` + `/leaves/balances/{id}` |
| Payroll | `GET /payroll/salaries/{id}` |
| Bank & Statutory | `GET /hr/employees/{id}/bank` + `/statutory` |

Header shows a `DRAFT` chip plus **`Complete profile →`** when `profile_status` is
`DRAFT`, dropping the user back into the wizard at Review.

Documents tab reuses the exact table from step 4, headed
**`Required Documents  7/8 Complete`**.

---

## 5. Document Management (dedicated HR page)

`GET /hr/documents/dashboard` → KPIs
`GET /hr/documents?status=&document_type=&employee_id=&department_id=&expiring_before=` → paginated register

```
Total 856    Verified 720    Pending 104    Rejected 22    Expired 10
                              ↑ default filter — this is the work queue

Filters: Employee · Document Type · Status · Department · Expiring before

Employee        Document        Uploaded     Status      Actions
Rahul Sharma    PAN             12 Aug       ⏳ Pending   [Verify] [Reject]
EMP-0007
```

- **Verify** → `POST /hr/documents/{id}/verify` with optional `{ expiry_date }`.
  Prompt for expiry only when the policy has `tracks_expiry`.
- **Reject** → `POST /hr/documents/{id}/reject` with `{ reason }` — **reason is
  mandatory**, so open a small dialog, never a bare confirm.

Both actions notify the employee automatically.

---

## 6. Settings → Document Policy

`GET /hr/document-policy` · `PUT /hr/document-policy`

```
Document Type          Required?   Tracks Expiry?   Active?
Resume                   [✓]           [ ]            [✓]
PAN                      [✓]           [ ]            [✓]
Aadhaar                  [✓]           [ ]            [✓]
Offer Letter             [✓]           [ ]            [✓]
Joining Letter           [✓]           [ ]            [✓]
Bank Proof               [✓]           [ ]            [✓]
Experience Letter        [ ]           [ ]            [✓]
Education Certificate    [ ]           [ ]            [✓]
Address Proof            [ ]           [ ]            [✓]
Work Permit              [ ]           [✓]            [✓]
Other                    [ ]           [ ]            [✓]
```

PUT sends the **whole array back**:

```jsonc
{ "policies": [ { "document_type": "AADHAAR", "is_required": false,
                  "tracks_expiry": false, "display_order": 3, "is_active": true } ] }
```

Warn before unticking Required on a type that employees are currently missing — it
silently completes profiles that were previously blocked.

---

## 7. Settings → Employee ID Format

Part of `PATCH /companies/current`:

```jsonc
{ "employee_id_format": "EMP-{NUMBER}", "employee_id_padding": 4 }
```

```
Format   [ EMP-{NUMBER} ]    Padding  [ 4 ]
Preview: EMP-0007, EMP-0008, EMP-0009      ← GET /hr/employee-code/preview?count=3
```

`{NUMBER}` is mandatory — the backend rejects a format without it with a clear message.
Live-preview as they type.

---

## 8. Import Employees

`GET /employees/csv-template` → downloadable template
`POST /employees/import` (multipart `file`)

```jsonc
{ "created": 12, "failed": 2, "created_employee_ids": [.....],
  "errors": [ { "row": 4, "error": "Department 'Sales' not found in this company" } ] }
```

Flow: **Upload → result summary → error table (row + reason) → Done**

Good rows commit even when others fail, so present it as a result, not an
all-or-nothing failure. Documents are **not** part of the CSV — upload them after.

---

## 9. Enums for dropdowns

| Field | Values |
|---|---|
| `document_type` | `RESUME` `AADHAAR` `PAN` `OFFER_LETTER` `JOINING_LETTER` `EXPERIENCE_LETTER` `EDUCATION` `ADDRESS_PROOF` `BANK_PROOF` `WORK_PERMIT` `LEAVE_ATTACHMENT` `OTHER` |
| `document status` | `PENDING` `VERIFIED` `REJECTED` `EXPIRED` |
| `profile_status` | `DRAFT` `COMPLETE` |
| `work_mode` | `OFFICE` `REMOTE` `HYBRID` |
| `employment_type` | `FULL_TIME` `PART_TIME` `CONTRACT` `INTERN` `CONSULTANT` |
| `employee status` | `ACTIVE` `PROBATION` `NOTICE_PERIOD` `INACTIVE` `TERMINATED` `RESIGNED` |
| `gender` | `MALE` `FEMALE` `OTHER` `UNDISCLOSED` |
| `marital_status` | `SINGLE` `MARRIED` `DIVORCED` `WIDOWED` `OTHER` |

Status chip colours: green `VERIFIED`/`ACTIVE`/`COMPLETE`, amber `PENDING`/`DRAFT`/`PROBATION`,
red `REJECTED`, grey `EXPIRED`/`INACTIVE`.

---

## 10. Build order

1. **Document policy settings** — everything else reads from it
2. **Employee ID format settings** — small, unblocks the wizard's step 3
3. **The wizard** — the biggest piece; steps 1–3 first, then 4, then 5–6
4. **Employee profile Documents tab** — reuses step 4's table
5. **Document Management page** — reuses the same row component
6. **HR dashboard** — mostly reads numbers you already render elsewhere

Steps 4, "profile → Documents" and the Document Management page are **the same table
three times**. Build `<DocumentChecklistTable>` once.

---

## Not in this milestone

- **Resume parsing (AI)** — MVP-3. `RESUME` is already a first-class document type, so
  parsing later just reads rows that exist.
- **Object storage** — files sit on local disk today; the database only ever holds
  metadata and a path, so swapping in S3 touches one backend file and nothing in the UI.
