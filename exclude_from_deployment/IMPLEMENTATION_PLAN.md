# MobileApp1 — Implementation Plan

**Stack:** Frappe v15 + ERPNext v15 · React Native · MariaDB · Redis · Zitadel SSO
**Total Duration:** 36 Weeks · 7 Phases · 29 Modules

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Summary](#2-architecture-summary)
3. [Phase 1 — Foundation & Environment (Weeks 1–2)](#3-phase-1--foundation--environment-weeks-12)
4. [Phase 2 — Master Data Management (Weeks 3–7)](#4-phase-2--master-data-management-weeks-37)
5. [Phase 3 — Operations & Transactions (Weeks 8–14)](#5-phase-3--operations--transactions-weeks-814)
6. [Phase 4 — Attendance & Field Tracking (Weeks 15–18)](#6-phase-4--attendance--field-tracking-weeks-1518)
7. [Phase 5 — Analytics, Reporting & Alerts (Weeks 19–23)](#7-phase-5--analytics-reporting--alerts-weeks-1923)
8. [Phase 6 — Mobile Application (Weeks 24–32)](#8-phase-6--mobile-application-weeks-2432)
9. [Phase 7 — Integration, QA & Launch (Weeks 33–36)](#9-phase-7--integration-qa--launch-weeks-3336)
10. [Open Questions](#10-open-questions)
11. [Tech Stack Reference](#11-tech-stack-reference)
12. [Key Implementation Rules](#12-key-implementation-rules)

---

## 1. Project Overview

MobileApp1 is a field sales force automation platform built on Frappe Framework with ERPNext as the ERP backend (referred to as **ZAP**). It consists of two codebases:

- **Admin Dashboard** — Frappe custom app (`mobileapp1`) installed alongside ERPNext on the same bench. Provides 17 dashboard modules for managers and admins.
- **Mobile Client** — React Native app consumed by field sales reps. Calls Frappe REST API, supports full offline-first operation via SQLite + outbox sync.

**Key design principle:** ERPNext-native first — reuse existing DocTypes (Expense Claim, Timesheet, Payment Entry, Journal Entry) before creating custom ones. Every phase ends with a working demo before the next begins.

---

## 2. Architecture Summary

| Component | Technology | Notes |
|---|---|---|
| Backend framework | Frappe v15 | Custom app: `mobileapp1` |
| ERP backend | ERPNext v15 | Same bench instance — no HTTP calls needed for writes |
| Database | MariaDB 10.6+ | Managed by Frappe bench |
| Cache / Queue | Redis 6+ | Background jobs + real-time |
| Mobile client | React Native (recommended) | Separate codebase |
| Mobile local DB | SQLite (react-native-sqlite-storage) | Mirrors key Frappe DocTypes |
| Mobile auth | Zitadel (OIDC/JWT) | JWT validated by Frappe custom middleware |
| Offline sync | SQLite outbox worker → Frappe REST | Idempotency keys + exponential backoff |
| File/image storage | Frappe File Manager or S3-compatible | Receipt images |
| External APIs | CMMS + CONNECT | Python adapter classes in `mobileapp1/adapters/` |
| Maps (admin) | Leaflet.js (CDN) | No install needed |
| Push notifications | Firebase Admin SDK (FCM) | Conditional — see Open Question #8 |
| CI/CD | GitHub Actions | Lint + tests on every PR |
| Error monitoring | Sentry | Frappe + mobile |
| Load testing | Locust or k6 | |
| Web server | Nginx + Gunicorn (bench-managed) | |

### Data Flow Overview

```
Mobile App (React Native)
    │  JWT (Zitadel)
    ▼
Frappe REST API  ──── Whitelist methods ────► mobileapp1 custom app
    │                                               │
    │  SQLite Outbox (offline)                      │─── Direct write ──► ERPNext DocTypes
    ▼                                               │                    (Payment Entry, JE,
Sync Worker (background)                            │                     Expense Claim, Timesheet)
    │                                               │─── HTTP call ──────► CMMS API
    └─────────────────────────────────────────────►│─── HTTP call ──────► CONNECT API
                                                    │
                                               Frappe Scheduler
                                               (alerts, sync jobs)
```

### Role Hierarchy

| Role | Access Level |
|---|---|
| MobileApp Admin | Full system access, configurations, user management |
| MobileApp Manager | Approval queues, reports, team visibility |
| Field Sales Rep | Mobile app only; own records only |

---

## 3. Phase 1 — Foundation & Environment (Weeks 1–2)

**Goal:** Running Frappe bench with ERPNext, custom app scaffolded, roles defined, CI/CD in place. No feature code yet.

### 1.1 Bench & ERPNext Setup

| Task | Deliverable | Notes |
|---|---|---|
| Provision Ubuntu 22 LTS server (8–16 GB RAM) | Server ready | Dedicated VM or cloud instance |
| `bench init` — install Frappe bench | Bench running | Python 3.11+, Node 18+ |
| Install ERPNext on bench | ERPNext accessible | Latest stable v15 |
| Create production site + SSL | HTTPS site live | Nginx + Let's Encrypt |
| Configure MariaDB, Redis, Supervisor | All services stable | `bench setup-production` |
| Enable Frappe Scheduler | Scheduler enabled | Required for all sync jobs |

### 1.2 Custom App Scaffold

| Task | Deliverable | Notes |
|---|---|---|
| `bench new-app mobileapp1` | App folder created | Python package structure |
| `bench install-app mobileapp1` on site | App installed | Verify in installed apps list |
| Git repo + branch strategy (`main/dev/feature/*`) | Repo live | GitHub / GitLab |
| Configure GitHub Actions CI (lint + basic tests on PR) | CI pipeline running | |
| Add pre-commit hooks (flake8, eslint) | Code quality gate | |

**Folder structure to create inside `mobileapp1/`:**
```
mobileapp1/
├── mobileapp1/
│   ├── adapters/
│   │   ├── cmms.py         # CMMS HTTP adapter
│   │   └── connect.py      # CONNECT HTTP adapter
│   ├── doctype/            # All custom DocTypes
│   ├── api/                # Whitelisted REST methods
│   ├── scheduled_tasks/    # Frappe scheduled jobs
│   └── utils/              # Shared helpers
```

### 1.3 ERPNext Base Configuration

| Task | Deliverable | Notes |
|---|---|---|
| Configure Company record (currency, fiscal year) | Company record | Matches client entity |
| Set up Chart of Accounts (Debit/Credit for cash & bank settlement) | Accounts ready | For Journal Entries |
| Configure Expense Claim Types | Expense types list | Maps to field rep expense categories |
| Configure Timesheet Activity Types | Activity types list | Used in M-10 timesheet sync |
| Enable only relevant ERPNext modules | Clean ERPNext UI | Disable unused modules |

### 1.4 Roles & Permissions Framework

| Task | Deliverable | Notes |
|---|---|---|
| Create custom roles: `MobileApp Admin`, `MobileApp Manager`, `Field Sales Rep` | 3 roles created | |
| Map to ERPNext roles where applicable (e.g. Manager → Accounts Manager for JE) | Role mapping doc | |
| Define permission matrix document (all DocTypes × roles) | Permission matrix | Reference for all future DocTypes |
| Create System Settings defaults (date format, IST timezone) | Settings locked | |

**Phase 1 exit criteria:** Frappe bench running, ERPNext accessible via HTTPS, `mobileapp1` app installed, 3 roles exist, CI passes on a dummy PR.

---

## 4. Phase 2 — Master Data Management (Weeks 3–7)

**Goal:** All master data DocTypes built, importable via CSV, manageable from admin dashboard. Mobile API contracts defined and documented.

### 2.1 D-01 · Geography Management

**DocType: `Geography`**

| Field | Type | Notes |
|---|---|---|
| Name | Data | Primary key |
| Level | Select | Zone / Region / Territory |
| Parent | Link → Geography | Self-referential |
| ERP ID | Data | |
| Status | Select | Active / Inactive |

**Tasks:**
- Set `is_tree=1` on DocType for built-in Frappe tree view
- Python controller: validate Zone → Region → Territory hierarchy at `save()` — raise `frappe.ValidationError` for violations
- List view filters: Level, Status
- REST endpoint: `GET /api/method/mobileapp1.api.geography.get_tree` (whitelisted, for mobile offline cache)

### 2.2 D-02 · User & Sales Rep Management

**Custom fields added to Frappe `User` DocType** (via Custom Field — never edit core):

| Field | Type | Notes |
|---|---|---|
| Employee ID | Data | Optional |
| Position | Link → Position | |
| Zone | Link → Geography | |
| Company Profile | Link → Company Profile | |
| IMEI | Data | Bound at first mobile login |
| User Type | Select | Admin / Manager / Field Rep |
| Module Access | Child Table | Drives mobile menu visibility |
| Warehouse Profile | Child Table | ZAP warehouses |
| App Access Toggle | Check | Independent of dashboard access |

**Child DocTypes:**
- `User Module Access` (User, Module: Invoicing / Payments / Timesheets / Connect / CMMS Retail / CMMS Vendor, Active)
- `User Warehouse Profile` (User, Warehouse Name, Type: ZAP read-only / CMMS editable)

**Tasks:**
- Dashboard access workflow: send activation code via email/SMS on user creation (Frappe Email Queue)
- Org-chart view (Reports-To tree) — custom Frappe desk page with JS tree
- REST endpoint: `GET /api/method/mobileapp1.api.user.get_profile` — returns module flags, IMEI, zone

### 2.3 D-03 · Position Management

**DocType: `Position`**

| Field | Type |
|---|---|
| Name | Data |
| Code | Data (PK) |
| Level | Select (L1–L4) |
| Reporting To | Link → Position (self-ref) |
| Attached Employee | Link → Employee |
| Status | Select |

**Child DocType: `Position Beat`** (bridge table: position_code + beat_code, composite unique constraint)

**Tasks:**
- Vacancy indicator: auto-derive from `Attached Employee` field — computed column in list view (SQL Report or override `get_list`)
- Attach/Detach beats UI on Position form (search dialog + child table)

### 2.4 D-04 · Beat / Route Management

**DocType: `Beat`**

| Field | Type | Notes |
|---|---|---|
| Name | Data | |
| Code | Data | |
| Type | Select | GT / MT |
| Territory | Link → Geography | Must be Level = Territory |
| ERP ID | Data | |
| Status | Select | |

**Child DocType: `Beat Outlet`** — Outlet assignment (one outlet = one beat enforced via validation)

**DocType: `Beat Schedule`** — day-of-week × ordered outlet list per beat (used to generate mobile daily plan)

**REST endpoint:** `GET /api/method/mobileapp1.api.beat.get_daily_plan?date=&rep=` — returns today's outlet list in order

### 2.5 D-05 · Outlet Management

**DocType: `Outlet`** — all fields per spec including GPS coordinates, mobile number (unique), Status

**Workflow:** Draft → Approved → Rejected (field-submitted outlets arrive as Draft; manager approves to Active)

**Tasks:**
- Last visit date: computed from Visit DocType, shown in list view (SQL Report or override `get_list`)
- Outlet form dashboard links: visits, orders, payments, asset requests
- CSV bulk import via standard Frappe Data Import Tool
- REST endpoint: `GET /api/method/mobileapp1.api.outlet.get_list?beat=` (mobile offline cache)

### 2.6 D-06 · Product Master

**DocType: `Product`**

| Field | Type | Notes |
|---|---|---|
| ERP ID | Data (PK) | Imported from ERPNext Item |
| Name | Data | |
| Division | Data | |
| Primary Category | Data | |
| Secondary Category | Data | |
| MRP | Currency | Read-only; fetched from ERPNext Item Price |
| GST Profile | Link → Item Tax Template | From ERPNext |
| Must-Sell | Check | Drives compliance reporting |
| Status | Select | |

**Tasks:**
- Price fetch: `frappe.get_doc('Item Price', ...)` on form load
- GST Profile display: linked ERPNext Item Tax Template
- Price visibility toggle (form script)
- CSV bulk import
- REST endpoint: `GET /api/method/mobileapp1.api.product.get_list` — returns active products with GST info

### 2.7 D-07 · Company Profile & Configurations

**DocType: `Company Profile`**

| Field | Notes |
|---|---|
| Code (PK) | |
| CONNECT API credentials | Stored encrypted, masked in UI |
| CMMS API credentials | Stored encrypted, masked in UI |
| Product alias mapping | Child DocType (CONNECT alias, CMMS alias per product) |
| Account alias mapping | Child DocType |

**Tasks:**
- Link Company Profile to User (mapped at user level)
- Test API connection buttons (CONNECT, CMMS) — whitelisted method returning success/fail
- Child DocType: `Product Alias Map`, `Account Alias Map`

**DocType: `System Configuration`** (Single DocType — `is_single=1`, Admin-only)

| Field | Notes |
|---|---|
| Payment Mode | Cash only / Online only / Cash + Online |
| Denomination Mandatory | Check — enforced in settlement controller |

**Phase 2 exit criteria:** All 7 master DocTypes CRUD, tree/list views working, CSV import tested, REST endpoints returning correct data, mobile API contract document published.

---

## 5. Phase 3 — Operations & Transactions (Weeks 8–14)

**Goal:** All transactional flows built with full approval workflows and ERPNext write-back. Most complex phase.

### 3.1 D-08 · Orders Management

**DocType: `Sales Order`** (custom — distinct from ERPNext SO)

Header fields: Flow Type (ZAP Invoice / CONNECT), Outlet, Beat, Rep, Visit, Status (PENDING → SUCCESS / FAILED)

**Child DocType: `Sales Order Item`**

| Field | Notes |
|---|---|
| Product | Link → Product |
| Qty | Int |
| MRP | Currency (fetched from cache) |
| CGST / SGST / IGST | Currency (auto-calculated from ERPNext Item Tax Template) |
| Net Value | Currency |

**Tasks:**
- ZAP sync: on approval, create ERPNext Sales Invoice via `frappe.get_doc().insert()` — direct write, no HTTP
- CONNECT sync: call `mobileapp1/adapters/connect.py` adapter on submission
- Sync status monitor view: PENDING/FAILED orders with manual retry button
- DocType: `No Order Reason` (reason category + text, linked to Visit)
- Order compilation Query Report (CSV/Excel export, filterable by product/beat/territory/rep)
- REST endpoint: `POST /api/method/mobileapp1.api.order.submit` — validates, stores, queues sync

### 3.2 D-09 · Payments Management

**DocType: `Payment Record`**

| Field | Notes |
|---|---|
| Amount | Currency |
| Mode | Select: Cash / Online / Cash+Online |
| Reference | Data |
| Outlet | Link |
| Rep | Link → User |
| Status | PENDING_APPROVAL → APPROVED → SUCCESS / FAILED |

**DocType: `Denomination Settlement`**

- Total amount
- Child table: denomination breakdown (₹2000 × N, ₹500 × N, etc.)
- Child table: bank/online references
- Target account

**DocType: `Credits & Partial Payments`** — credit note / partial against outlet, running balance

**Tasks:**
- Payment approval queue: manager list view with Approve/Reject actions (Frappe Workflow)
- On approval: create ERPNext Payment Entry via `frappe.get_doc().insert()` — direct write
- Denomination logic: mandatory for cash settlements (read `System Configuration.denomination_mandatory`), `frappe.throw()` if not filled
- Settlement approval: on approve, create ERPNext Journal Entry (Debit: collection account, Credit: cash/bank)
- Aggregated credit balance shown on Outlet form
- REST endpoints: `POST /api/method/mobileapp1.api.payment.submit`, `POST /api/method/mobileapp1.api.settlement.submit`

### 3.3 D-10 · Expenses & Reimbursements

**Approach:** Extend ERPNext `Expense Claim` DocType with custom fields (no new DocType).

**Custom fields added:**
- Receipt Image URLs (child table or text)
- Sync Status

**Tasks:**
- Expense approval queue: list view filtered to PENDING_APPROVAL claims
- On approval: submit ERPNext Expense Claim via frappe workflow submit — ERPNext handles GL entry
- Receipt image: upload to Frappe File Manager (or S3), store URL via `frappe.attach_file()`
- REST endpoints: `POST /api/method/mobileapp1.api.expense.submit`, `POST /api/method/mobileapp1.api.expense.upload_receipt`

### 3.4 D-11 · Timesheets

**Approach:** Extend ERPNext `Timesheet` DocType with custom fields.

**Custom fields added:**
- Sync Status
- Mobile Submission Flag

**Tasks:**
- Timesheet approval queue: manager list view, Approve/Reject actions (Frappe Workflow)
- On approval: submit ERPNext Timesheet — ERPNext handles salary/payroll linkage
- REST endpoint: `POST /api/method/mobileapp1.api.timesheet.submit`

### 3.5 D-12 · Prop / Asset & Material Requests

**DocType: `Material Request`** (custom — distinct from ERPNext MR)

| Field | Notes |
|---|---|
| Type | Data |
| Item | Data |
| Qty | Int |
| Outlet | Link |
| Notes | Text |
| Status | PENDING_APPROVAL → APPROVED → REQUEST_CREATED → DEPLOYED / FAILED |

**DocType: `Asset Capitalization Request`** — no approval needed; goes direct to CMMS queue

| Status | PENDING → REQUEST_CREATED → DEPLOYED / FAILED |

**DocType: `Vendor`**

| Field | Notes |
|---|---|
| Name | Data |
| Contact | Data |
| Mobile | Data |
| Email | Data |
| Category | Data |
| Status | Select |
| CMMS Supplier | Link |

**Child DocType: `Vendor Employee`** — inherits CMMS Supplier details

**Tasks:**
- Material request approval workflow (manager approve → CMMS sync)
- CMMS adapter: `mobileapp1/adapters/cmms.py` — async via Frappe job queue
- CMMS webhook receiver: whitelisted POST endpoint to receive deployment status updates, write back status
- Prop request timeline view: custom Frappe desk page (HTML + JS timeline component) showing lifecycle timestamps
- REST endpoints: `POST /api/method/mobileapp1.api.material_request.submit`, `GET /api/method/mobileapp1.api.material_request.get_status`

**Phase 3 exit criteria:** Full order-to-ERP, payment-to-ERP, expense-to-ERP, timesheet-to-ERP flows verified in staging. CMMS adapter connected and tested. All approval queues functional.

---

## 6. Phase 4 — Attendance & Field Tracking (Weeks 15–18)

**Goal:** Full attendance logging, GPS visit records, map visualization, and daily journey view operational.

### 4.1 D-13 · Attendance Tracking

**DocType: `Attendance Log`**

| Field | Notes |
|---|---|
| Rep | Link → User |
| Date | Date |
| Mark Time | Datetime |
| GPS Lat | Float |
| GPS Lng | Float |
| Status | Present / Absent / Late |

**Tasks:**
- One record per rep per day (unique constraint on Rep + Date)
- Daily attendance list view: per rep — marked/not marked, GPS, timestamp
- Attendance calendar view: monthly per rep — custom Frappe desk page using FullCalendar or simple grid
- Team attendance summary widget: manager sees all reps in territory, attendance % (Query Report)
- Attendance report export (CSV with GPS + timestamps)
- Frappe scheduled job: flag reps with no attendance for the day (runs at end-of-day cutoff, feeds D-16 alerts)
- REST endpoint: `POST /api/method/mobileapp1.api.attendance.mark` — accepts GPS coords + timestamp

### 4.2 D-14 · Location & Visit GPS Tracking

**DocType: `Visit GPS Record`**

| Field | Notes |
|---|---|
| Rep | Link → User |
| Outlet | Link → Outlet |
| Check-in Lat/Lng | Float |
| Check-out Lat/Lng | Float |
| Distance from Outlet | Float (metres) |
| Timestamp | Datetime |
| Out-of-range Flag | Check |

**Tasks:**
- Out-of-range detection: compare check-in coords vs Outlet registered coords using **Haversine formula** in controller; flag if > threshold
- GPS records list view with out-of-range filter
- Map view: custom Frappe desk page embedding **Leaflet.js** (CDN); plots outlet pin vs actual check-in pin
- Daily rep journey view: chronological outlet sequence for a rep on a given day (ordered by check-in timestamp)
- REST endpoints: `POST /api/method/mobileapp1.api.visit.checkin`, `POST /api/method/mobileapp1.api.visit.checkout`

**Phase 4 exit criteria:** Attendance marking working, GPS visit records created on check-in/out, out-of-range detection firing, map view rendering outlet vs check-in pins.

---

## 7. Phase 5 — Analytics, Reporting & Alerts (Weeks 19–23)

**Goal:** All reports, dashboards, and alert systems operational.

### 5.1 D-15 · Performance & Sales Analytics

All reports are **Frappe Query Reports** (SQL-based, CSV/Excel export):

| Report | Key Filters |
|---|---|
| Rep Performance | Rep, date range, territory — visits/day, order hit rate, productive vs non-productive, must-sell compliance |
| Sales Analysis | Product / category / beat / territory / channel, period comparison |
| Order Compilation | Daily/weekly/monthly, beat/outlet/product/category breakdown |
| Payment Collections | Rep, mode, status, date range |
| Productivity KPI | Coverage %, strike rate, avg time per visit, outlier detection (2 std dev below mean) |
| Asset/Prop Report | Status, type, outlet, territory |

**DocType: `Target`** (conditional — see Open Question #2)
- Fields: Rep / Beat / Product link, Period, Target Qty, Target Value
- Actual derived from Orders

**Frappe Dashboard:** Single admin home page with KPI number cards + charts assembled from Query Reports.

**Filter standardization:** All reports must share the same parameter names (`rep`, `date_from`, `date_to`, `territory`, `beat`).

### 5.2 D-16 · Alerts & Notifications

**DocType: `Notification Preference`**

| Field | Notes |
|---|---|
| User | Link |
| Alert Type | Select |
| Channel | In-app / Email / Push |
| Active | Check |

**Alert types and triggers:**

| Alert | Trigger |
|---|---|
| Approval pending | Frappe scheduled job counts pending records; pushes `frappe.publish_realtime()` |
| Sync failure | CMMS/CONNECT adapter on failure after retries; creates Alert Log DocType entry |
| Rep inactivity | Scheduled job checks attendance + visit logs; flags inactive reps |
| Prop status change | Triggered by CMMS webhook receiver |

**Channels:**
- **In-app:** `frappe.publish_realtime()` + Frappe built-in notification bell
- **Email:** Frappe Email Queue with templated emails
- **Push (FCM):** Firebase Admin SDK integration — conditional on Open Question #8

**Phase 5 exit criteria:** All 6 Query Reports returning correct data, Frappe Dashboard assembled, at least 3 alert types firing correctly in staging.

---

## 8. Phase 6 — Mobile Application (Weeks 24–32)

**Goal:** Full React Native mobile app connected to Frappe backend. All 12 modules functional, offline-first sync working end-to-end.

### 6.0 Mobile Project Setup

**Tasks:**
- Initialize React Native project, set up folder structure
- SQLite local storage layer (`react-native-sqlite-storage`); schema mirrors key Frappe DocTypes

**SQLite tables to create:**
```
outbox          (id, job_type, payload JSON, status, retry_count, idempotency_key, created_at)
beats           (mirrors Beat + Beat Schedule)
outlets         (mirrors Outlet)
products        (mirrors Product)
visits          (local visit records)
orders          (local order records)
account_maps    (mirrors Account Alias Map)
```

- Outbox queue module: central to all offline sync
- Sync worker: background service; reads outbox, calls Frappe REST API, handles retries (exponential backoff, max 5 retries, then mark FAILED)
- Zitadel JWT auth: login screen, token storage (Keychain/Keystore), auto-refresh
- IMEI capture: `react-native-device-info` on first login; Frappe validates and binds to User record
- Master data sync on login: fetch and cache beats, outlets, products, account maps to SQLite; periodic background refresh
- Offline indicator component + sync status bar (shows pending count, last sync time)

### 6.1 M-01 + M-02 · Auth & Attendance

| Screen | Behaviour |
|---|---|
| Login | Username/password → Zitadel → JWT → secure storage |
| IMEI Binding | First-login flow: send IMEI, receive confirmation |
| Attendance Mark | Single tap; captures GPS; stores SQLite + outbox; **required before home screen shown** |
| Attendance Calendar | Own history; present/absent days colour-coded |
| Session Manager | Stays logged in; re-prompts only if token unrefreshable |

### 6.2 M-03 · Home Screen

| Component | Notes |
|---|---|
| Module tiles | Retailing / Official Work / Attendance — driven by module access flags from User profile |
| Today's summary card | Visits, orders, payments, pending sync count — read from local SQLite |
| Notification bell | In-app notifications from Frappe realtime or polled API |
| Offline indicator | Status bar component |

### 6.3 M-04 + M-05 · Visit Management & Outlet Registration

| Screen | Behaviour |
|---|---|
| Beat plan | Today's outlet list from SQLite cache; planned vs visited count |
| Check-in | Select outlet → capture GPS → distance check → timestamp → store SQLite + outbox |
| Check-out | Calculate time spent → store visit record in outbox |
| Telephonic visit toggle | Bypass GPS requirement; flag on record |
| Visit history | Per outlet |
| New outlet registration | All fields; stores locally as draft; syncs to Frappe approval queue |
| Outlet registration status | Submitted / Approved / Rejected |

### 6.4 M-06 · Order Taking

| Screen | Behaviour |
|---|---|
| Order header | Select flow (ZAP Invoice / CONNECT); auto-fill outlet/beat/visit |
| Product search | Search by name/category; enter qty |
| Line item | Price (read-only from cache); tax auto-calculated per line |
| Must-sell compliance | Highlight missing must-sell SKUs; show alert |
| No-order reason | Prompt if no items added before check-out |
| Sync flow | Order stored in SQLite + outbox; sync to Frappe; status tracked |
| Order history | List screen |

### 6.5 M-07 · Payment Collection

| Screen | Behaviour |
|---|---|
| Payment submission | Mode selector (per System Config); amount; reference |
| Denomination settlement | Total amount; denomination breakdown; bank/online references; target account; denomination mandatory for cash (config-driven) |
| Credit/partial payment | Record against outlet; show running balance |
| Payment status | PENDING_APPROVAL → APPROVED → SUCCESS / FAILED |
| Payment history | List screen |

### 6.6 M-08 + M-09 + M-10 · Props, Expenses, Timesheets

| Module | Screen | Notes |
|---|---|---|
| M-08 Material Request | Request form | Type, item (from cache), qty, outlet, notes |
| M-08 | Timeline | Submitted → Approved → Created → Deployed |
| M-09 Expenses | Expense form | Type, amount, date, description + receipt camera/gallery upload → Frappe file API |
| M-10 Timesheets | Timesheet form | Period from/to, hours, activity, notes |
| M-09 + M-10 | Status screens | Approval status tracking |

### 6.7 M-11 · Official Work

| Screen | Behaviour |
|---|---|
| Official work log form | Activity type, description, duration, date (GPS optional — see Open Question #1) |
| Official work history | List screen |
| Sync flow | Outbox pattern |

### 6.8 M-12 · Offline Sync Engine (Polish)

**Outbox coverage audit** — verify all record types go through outbox:
- Visits, Orders, Payments, Attendance, Expenses, Timesheets, Asset Requests, Outlet Registrations

**Idempotency:** UUID generated per record on creation; sent with every API call; Frappe deduplicates on receipt.

**Retry logic:** Exponential backoff; max 5 retries; then mark FAILED + surface in sync status screen.

**Sync status screen:** Pending count, last sync time, failed items list with error detail.

**Master data refresh:** Periodic background pull of beats/outlets/products when online.

**Phase 6 exit criteria:** All 12 mobile modules functional. Golden path (login → attendance → check-in → order → payment → check-out) tested end-to-end with real Frappe backend. Offline-then-sync tested for every record type.

---

## 9. Phase 7 — Integration, QA & Launch (Weeks 33–36)

**Goal:** Production-ready system. All integrations hardened, E2E testing passed, UAT signed off, performance validated, production deployed.

### 7.1 External Integration Hardening

| Task | Notes |
|---|---|
| CMMS adapter: full retry logic, structured error logging, webhook signature validation | Production-grade |
| CONNECT adapter: full retry logic, error logging, timeout handling | Production-grade |
| Sync failure alert pipeline: E2E test (adapter fails → alert fires → admin sees it) | |
| CMMS webhook: replay protection (idempotency check on incoming webhooks) | Dedup logic |
| API credential rotation procedure documented | Runbook |

### 7.2 End-to-End & Integration Testing

| Test Suite | Tool | Coverage |
|---|---|---|
| Frappe unit tests for all custom controllers + whitelisted methods | pytest (`frappe.tests`) | |
| Mobile integration tests: key user journeys | Detox or Appium | login → check-in → order → payment → check-out |
| Offline sync E2E | Custom | Create offline, restore connectivity, verify all sync |
| ERPNext write-back tests | Integration tests | Payment Entry, Journal Entry, Expense Claim, Timesheet created correctly |
| Permission matrix test | Custom | Verify each role can/cannot access correct DocTypes/actions |
| Load test: 50+ concurrent mobile sync workers | Locust or k6 | Hitting Frappe REST API |

### 7.3 UAT & Bug Fixes

| UAT Stream | Focus |
|---|---|
| Field sales reps (mobile) | Check-in, order, payment flows |
| Managers | Approval queues, reports, alerts |
| Admins | Master data, configurations, user management |

**Bug triage and fix sprint:** 2-week buffer built into schedule. Target: zero P0/P1 bugs before launch.

### 7.4 Performance & Production Readiness

| Task | Notes |
|---|---|
| DB index review: add indexes on `rep`, `date`, `status`, `outlet`, `beat` | `EXPLAIN ANALYZE` on slow queries |
| Redis cache for master data API responses | `frappe.cache().get_value()` |
| Mobile APK/IPA build pipeline | GitHub Actions; generates signed builds |
| Production deployment: `bench migrate` + restart | Off-peak deployment window |
| Monitoring: Sentry (errors), Uptime monitor, Frappe Error Log alerts | |
| Backup and DR procedure tested | `bench backup` + offsite storage |
| Handover documentation: admin guide, developer guide, API reference | |

**Phase 7 exit criteria:** All tests passing, UAT sign-off received from all 3 user groups, load test at 50+ concurrent users passing, production site live, monitoring active.

---

## 10. Open Questions

These must be resolved **before the blocking phase begins**. Unresolved questions will stall development.

| # | Question | Detail | Blocks | Priority |
|---|---|---|---|---|
| 1 | **Official Work scope** | Activity types defined? GPS required? Manager approval needed? | Phase 6 M-11 | High |
| 2 | **Targets required?** | Yes/no. If yes: per user/beat/product, monthly/weekly? | Phase 5 D-15 | Medium |
| 3 | **Attendance logic** | Single tap or auto on first check-in? Check-out required? | Phase 4 D-13, M-02 | High |
| 4 | **Outlet approval** | Field-registered outlets — manager approval or immediate? | Phase 2 D-05, Phase 6 M-05 | High |
| 5 | **Credits & partial payments** | Credit = negative payment? Against invoice or outlet balance? ZAP sync? | Phase 3 D-09, M-07 | High |
| 6 | **Vendor onboarding scope** | Full CRUD entity? Multi-step onboarding with documents? | Phase 3 D-12 | Medium |
| 7 | **Location tracking mode** | Real-time GPS (WebSocket) or historical visit GPS only? | Phase 4 D-14 | High |
| 8 | **Push notifications** | FCM/APNs required or in-app bell only? | Phase 5 D-16, Phase 6 | Medium |
| 9 | **Official Work — approval** | Does logging require manager approval? Syncs to ERPNext? | Phase 6 M-11 | Medium |
| 10 | **Payment mode — Cash+Online** | Confirm three modes. How are denominations + online refs captured simultaneously? | Phase 3 D-09, Phase 6 M-07 | High |

---

## 11. Tech Stack Reference

| Component | Version / Tool |
|---|---|
| Frappe | v15 (latest stable) |
| ERPNext | v15 (same bench) |
| Python | 3.11+ |
| Node.js | 18+ (Frappe assets build) |
| Database | MariaDB 10.6+ |
| Cache / Queue | Redis 6+ |
| Web Server | Nginx + Gunicorn (bench-managed) |
| Mobile Framework | React Native (recommended) or Flutter |
| Mobile Local DB | SQLite via react-native-sqlite-storage |
| Mobile Auth | Zitadel (OIDC/JWT) |
| Maps (admin) | Leaflet.js (CDN) |
| File / Image Storage | Frappe File Manager (local) or S3-compatible |
| Push Notifications | Firebase Admin SDK (FCM) — if push confirmed |
| CI/CD | GitHub Actions |
| Error Monitoring | Sentry (Frappe + mobile) |
| Load Testing | Locust or k6 |

---

## 12. Key Implementation Rules

1. **ERPNext-native first.** Reuse existing DocTypes (Expense Claim, Timesheet, Payment Entry, Journal Entry) before creating custom ones. Extend with Custom Fields; never edit ERPNext core.

2. **No phase starts until the previous one is tested and demo'd.** Each phase produces a shippable, testable output.

3. **Mobile API contracts frozen at end of Phase 2.** Mobile development can begin in parallel from Phase 3 onward.

4. **Adapter pattern for all external integrations.** CMMS and CONNECT calls go through `mobileapp1/adapters/cmms.py` and `mobileapp1/adapters/connect.py`. Business logic never calls external APIs directly.

5. **ZAP (ERPNext) writes are direct — no HTTP.** Use `frappe.get_doc().insert()` / `.submit()` / `.save()`. No REST calls between the custom app and ERPNext since they share the same bench.

6. **Roles and permissions configured from day one.** The permission matrix (all DocTypes × roles) is built in Phase 1 and applied to every new DocType immediately — never retrofitted at the end.

7. **All outbox records carry an idempotency key.** UUID generated on record creation, sent on every sync attempt. Frappe endpoint deduplicates on this key.

8. **Async for all external API calls.** CMMS and CONNECT calls go through the Frappe job queue — never block a web request.

9. **Encrypted credentials.** Company Profile stores CMMS and CONNECT API credentials encrypted. Never expose in plain text in the UI.

10. **Universal filter naming.** All Query Reports share the same parameter names: `rep`, `date_from`, `date_to`, `territory`, `beat`. Establish this in Phase 5 before any reports are built.

---

*Document generated: May 2026 — Internal Use Only*
