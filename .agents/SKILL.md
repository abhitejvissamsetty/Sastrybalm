---
name: sastrybalm-erp
description: >-
  FMCG Sales & Distribution ERP system workflow guide. Covers Warehouses,
  Geographies (Zones, Regions, Territories), Position Hierarchy (L1-L4) with
  Warehouse inheritance resolution, Beat Routing, Products & Inventory,
  Vendors, User Roles, Sidebar Navigation, and User Management forms.
---

# Sastrybalm ERP — Sales & Distribution System Guide

## Overview
Sastrybalm ERP is a comprehensive FMCG Sales & Distribution Management System built with **FastAPI**, **SQLAlchemy**, **Jinja2 Templates**, and **MySQL (MAMP)**.

The system orchestrates:
- **Geography Management**: Multi-tier hierarchy (`Zone` → `Region` → `Territory`).
- **Warehouse Infrastructure**: Regional depots attached to Geographies, multi-warehouse product stock tracking, and stock movement auditing.
- **Position Hierarchy**: 4-level organizational hierarchy (`L1` to `L4`) with automatic reporting parent warehouse inheritance resolution.
- **Beat & Outlet Management**: Field routes (`GT` / `MT`) assigned to `L1 Positions` and mapped to `Outlets`.
- **Product & Inventory System**: Product cataloging with PTR (Price to Retailer) pricing, category scopes (`Sales`, `Marketing - Procurement`, `Marketing - Stock`), multi-warehouse stock allocation, and zero-stock deactivation guardrails.
- **Vendor Operations**: Specialized vendor supply management scoped to `Marketing - Procurement` products.
- **User Roles & Scope Matrix**: Granular permissions matrix for Admin, Territory Manager, Field Rep, QC Manager, Vendor Admin, and Vendor Technician.
- **Sidebar Navigation Order**: Standardized section hierarchy for optimal ERP UX.

---

## 🏛️ System Architecture & Data Models

### Database Connection
- **DB Engine**: MySQL (MAMP default on `127.0.0.1:8889`, database `sastrybalm_db`, user `root`, password `root`).
- **ORM Base**: SQLAlchemy 2.0.
- **Migration Script**: `PYTHONPATH=. ./venv/bin/python db_migrate.py`

### Key Models & Relationships

```mermaid
erDiagram
    GEOGRAPHY ||--o{ GEOGRAPHY : "parent (Zone -> Region -> Territory)"
    GEOGRAPHY ||--o{ WAREHOUSE : "attached_warehouses (Region level)"
    WAREHOUSE ||--o{ PRODUCT_WAREHOUSE_STOCK : "stocks"
    PRODUCT ||--o{ PRODUCT_WAREHOUSE_STOCK : "warehouse_stocks"
    POSITION ||--o{ POSITION : "reporting_to (L1 -> L2 -> L3 -> L4)"
    POSITION }|--|| WAREHOUSE : "assigned_warehouse (Optional)"
    POSITION }|--|{ BEAT : "beats"
    BEAT ||--o{ OUTLET : "outlets"
    USER }|--|{ POSITION : "positions"
    VENDOR }|--|{ PRODUCT : "supplied_products (Marketing Procurement)"
```

---

## 📍 1. Geography & Regional Warehouse Architecture

### Hierarchy Rules
1. **Zone**: Top-level geography node (`parent_id = None`).
2. **Region**: Mid-level node; **MUST** report to a `Zone`.
3. **Territory**: Field-level node; **MUST** report to a `Region`.

### Regional Warehouses & Permission Resolution
- Warehouses are assigned directly at the **Region** level (`Geography.level == GeoLevel.region`).
- **Mandatory Region Warehouse Rule**: A Region **MUST** contain at least one attached Warehouse mandatorily during creation (`/geography/new`) and editing (`/geography/{id}/edit`). Saving a Region without selecting at least one warehouse is rejected with a validation error.
- **Territory Manager Warehouse Resolution**: Permission to access, inward, and adjust inventory for warehouses is resolved directly from the **Region** (`geography_id`) assigned to the Territory Manager. Any warehouse attached to that Region (`Warehouse.geography_id == User.geography_id`) is automatically accessible by that Territory Manager, eliminating the need for direct per-user warehouse assignments.

---

## 👔 2. Position Hierarchy & Warehouse Resolution

### Position Levels
- **L4**: Top-level executive management (`reporting_to_id = None`).
- **L3**: Regional management (reports to `L4`).
- **L2**: Area/Territory management (reports to `L3`).
- **L1**: Field sales representative / Beat execution level (reports to `L2`).

### Warehouse Resolution Algorithm (`resolve_warehouse`)
When an **Outlet** places an Order, Asset Request, or Material Request:
1. Identify the **L1 Position** linked to the Outlet's **Beat Route**.
2. Execute `position.resolve_warehouse()`:
   - Check if the **L1 Position** has a directly assigned active `warehouse_id`.
   - If not, traverse up the `reporting_to` hierarchy: **L2** → **L3** → **L4**.
   - Return the first active `Warehouse` found along the parent reporting chain.
3. **L1 Position Save Validation**:
   - Saving an `L1 Position` requires that a valid warehouse can be resolved (either directly assigned or inherited from its reporting parent hierarchy L2/L3/L4). If no warehouse is resolved, saving is rejected with a validation error.

---

## 📦 3. Product Catalog & Inventory Rules

### Category Scopes (`ProductCategory`)
- **Sales**: Core commercial FMCG products sold to retailers/outlets via Beats.
- **Marketing - Procurement**: Specialized promotional items supplied by external Vendors.
- **Marketing - Stock**: Promotional marketing items stored in warehouses.

### Pricing & Terminology
- **MRP**: Maximum Retail Price.
- **PTR**: Price to Retailer (replaces Unit Cost across UI forms, inventory tables, and reports).

### Multi-Warehouse Stock Management
- Products can be attached to multiple warehouses via the dedicated **Attach Warehouses** dual pick-list interface (`/products/{product_id}/attach-warehouses`).
- Each warehouse maintains independent stock quantities (`ProductWarehouseStock`).
- **Stock Deactivation Guardrail**: A product cannot be deactivated if there is remaining stock present across any warehouse. Attempting to deactivate a stocked product triggers a dashboard-styled modal alert.

---

## 🏬 4. Vendors & Scope Control

- **Vendor Product Scope**: Restricted strictly to products with `category_type == ProductCategory.marketing_procurement`.
- **Vendor Geography Scope**: Vendor geography scope is strictly limited to **Regions** (`GeoLevel.region`). Forms and dropdowns filter available geographies exclusively to Region-level nodes.
- **Regional Scope Resolution**: Vendors managed by a **Territory Manager** are resolved and filtered directly by the `geography_id` (Region) field on the `Vendor` model (`Vendor.geography_id == User.geography_id`). Vendors created by a Territory Manager are automatically tagged with their assigned Region.
- **Vendor Users**: Mobile and web logins for `Vendor Admin` and `Vendor Technician` roles.

---

## 👥 5. User Roles, Scope Matrix & User Management Forms

### Permissions Matrix
| Role (`UserRole`) | Scope & Administrative Controls |
| :--- | :--- |
| **`admin`** | **Full Administrative Access**: Authorized to create, edit, deactivate, or manage all Master Data (Geographies, Warehouses, Users, Products, Positions L1-L4, Beats, Vendors, Sales Channels, SMTP/System Settings). |
| **`territory_manager`** | **Regional Management Scope**: Assigned to a specific Region (`Geography`). <br>• **Warehouse Access Resolution**: User permission to access, inward, and adjust inventory for warehouses is resolved directly from their assigned **Region** (`User.geography_id`). Any warehouse attached to that Region (`Warehouse.geography_id == User.geography_id`) is automatically accessible by that Territory Manager. <br>• **Vendor Access Resolution**: Vendors managed by a Territory Manager are resolved and filtered directly by the `geography_id` (Region) field on the `Vendor` model (`Vendor.geography_id == User.geography_id`). <br>• **Allowed Actions**: Can create/edit **L1 Positions**, create/edit **Channel Partners**, create/edit **Field Rep Users**, create/edit **Beats & Routes**, attach beats to L1 positions, create/edit **Vendors** in their region, and perform **Inventory Inwarding & Stock Adjustments** for warehouses attached to their assigned region. <br>• **Restricted Actions**: Cannot create/edit/deactivate Geographies, Warehouses, Admin/TM Users, Products, or L2–L4 Positions. |
| **`field_rep`** | **Field Mobile Execution**: Beat route visits, order taking, outlet creation, attendance, and expense submissions. |
| **`qc_manager`** | **Quality Control**: Audit logs & quality inspections. *(Hides position hierarchy selector)* |
| **`vendor_admin`** | **Vendor Operations**: Material request processing & vendor employee management. *(Hides position hierarchy selector)* |
| **`vendor_technician`** | **Vendor Field Tech**: Installation & asset maintenance. *(Hides position hierarchy selector)* |

### User Form Configuration Rules (`/users/new` and `/users/{id}/edit`)
1. **Company Profile Removed**: Company profile selection is excluded from user creation and editing forms.
2. **Assigned Positions Search**: Real-time text search input (`#position-search-input`) inside `#position-hierarchy-container` filtering positions by name or level badge (`L1`, `L2`, etc.).
3. **Active Checkbox Removal**: The `is_active` checkbox is removed from the User Edit form. Account status toggling is managed exclusively via `Deactivate` / `Activate` action buttons in the User List table (`/users`). Updates via `/users/{id}/edit` preserve existing active status.

---

## 🧭 6. Sidebar Navigation Section Hierarchy

The sidebar layout (`app/templates/shared/sidebar.html`) follows a standardized vertical section ordering:
1. **Dashboard**
2. **Field Tracking** *(Attendance, Visit Records, GPS Map View)*
3. **Operations** *(Orders, Expenses, Timesheets, Material Requests, Marketing Assets)*
4. **Analytics** *(Sales Analytics, Rep Performance, Marketing, Alerts, Approvals Hub, Auto-Flags)*
5. **Catalogue** *(Products, Inventory, Warehouses)*
6. **Master Data** *(Geography, Users & Reps, Positions, Beats & Routes, Outlets, Channel Partners, Vendors)*
7. **Configuration** *(Sales Channels, SMTP Settings, Webhooks, WhatsApp API, Data Backup)*
8. **Developer** *(Mobile API Docs)*

---

## 🤝 7. Channel Partners Rules & Mandates

- **Mandatory Geography Scope**: Every Channel Partner must be assigned to a Geography node scoped strictly to **Territory** (`GeoLevel.territory`) or **Region** (`GeoLevel.region`). Saving a Channel Partner without a valid Territory/Region geography scope is rejected.
- **Mandatory Multi-Select Sales Channels**: Every Channel Partner must have at least one **Sales Channel** selected from the available beat types (e.g. `GT`, `MT`). Selection is mandatory during creation and edits.
- **Active Status Action Buttons**: The `is_active` checkbox is removed from the Channel Partner edit form. Status toggling is managed strictly via `Deactivate` / `Activate` action buttons in the Channel Partners list table (`/channel-partners`). Updates via form preserve existing active status.
- **Manual Channel Partner Allocation by Field Rep**: Channel Partner allocation on order placement (web & mobile API) is **manual**, selected explicitly by the Field Rep from active Channel Partners operating in that territory. No initial notification is sent upon submission.
- **Configurable Auto-Approval Cutoff Time (`/settings/approval-rules`)**: Configured in Configuration tab via `auto_approval_cutoff_hours` (default `24` hours). Submitted orders remain in pending approval state until manually approved by a Territory Manager/Admin or auto-approved by background scheduler post cutoff window.
- **Pre-Approval TM Authority**: Before cutoff expiration, Territory Managers can edit order details, modify line items, reassign the Channel Partner, and manually approve or reject the order.
- **Approval-Triggered Instant Notifications**: Instant order notifications trigger **strictly upon Order Approval** (manual approval or post-cutoff auto-approval). Dispatched to the allocated Channel Partner via their assigned delivery service (`notification_channel`).
- **Post-Approval Reassignment by TM**: Territory Managers and Admins retain authority to reassign the fulfillment Channel Partner post-approval via `/orders/{id}/allocate-channel-partner`. Reassignment post-approval dispatches an instant order notification to the newly assigned Channel Partner.
- **Order Life-Cycle Audit Log**: Every order maintains a detailed audit history log (`order_history_logs` table) recording timestamps, action events (`created`, `status_changed`, `channel_partner_allocated`, `auto_approved_cutoff`, `channel_partner_reassigned_post_approval`), status transitions, user, and notes.
- **Preferred Delivery Service Assignment**: Each Channel Partner can be explicitly assigned their preferred notification delivery service (`notification_channel`):
  1. **Email via System SMTP (`/settings/smtp`)**: Dispatches instant order alert emails and daily summary CSV attachments directly to `ChannelPartner.email`.
  2. **WhatsApp Business API (`/settings/whatsapp`)**: Sends instant order receipts and summary document links directly to `ChannelPartner.mobile`.
  3. **Both Email & WhatsApp**: Dispatches dual alerts across SMTP Email and WhatsApp API simultaneously.
  4. **Webhook API (`/settings/webhooks`)**: Pushes real-time JSON order event payloads to external Channel Partner systems/ERPs.
  5. **On-Demand Web Export (`/channel-partners`)**: Instant manual download of consolidated CSV files via dashboard `CSV` button.

---

## 📦 8. Material Requests & Vendor Procurement Mandates

- **Regional+ Vendor Mapping Scope**: Material Request vendor mapping and reassignments (`/material-requests/{id}/assign-vendor`) are restricted to **Territory Managers whose assigned geography level is Region or higher** (`GeoLevel.region` or `GeoLevel.zone`) and **Admins**. Reassignments are permitted at any stage before Work Order completion / QC Manager approval.
- **Vendor Material Request Notifications**: Once a Material Request is assigned to a vendor AND approved, instant notification is dispatched to the assigned vendor via their configured delivery system (Email SMTP, WhatsApp API, Webhook). Post-approval reassignments trigger instant notification to the newly assigned vendor.
- **Material Request Audit Log**: Every Material Request maintains a detailed history log (`material_request_history_logs` table) tracking actions (`created`, `vendor_assigned`, `vendor_reassigned`, `status_changed`, `quotation_submitted`, `work_order_created`, `qc_approved`, `qc_failed`), status transitions, user, and notes.
- **Quotations & Work Orders Schemas & Role Access**: Vendor Quotations (`vendor_quotations`) and Work Orders (`work_orders`) schemas support bidding, issuance, and verification. Access is granted to `vendor_admin`, `vendor_technician`, `qc_manager`, `territory_manager`, and `admin`.
- **QC Manager Photo Verification**: Work Order QC completion (`/material-requests/work-orders/{wo_id}/qc` & mobile API `/api/v1/work-orders/{wo_id}/qc-approve`) requires photo inspection upload (`qc_photo_url`). Upon QC approval, the system itemizes stock inward and automatically converts the item to a Marketing Asset.
- **Database Storage Mandate for All System Configurations**: ALL system configurations and settings MUST be persisted strictly to the MySQL database (not stored in flat files, `.env` overwrites, or volatile in-memory caches). This includes SMTP Email Settings (`/settings/smtp`), Order Auto-Approval Cutoff Rules (`/settings/approval-rules`), Backblaze B2 S3 Storage (`/settings/s3`), WhatsApp Business API Credentials (`/settings/whatsapp`), Webhooks (`/settings/webhooks`), Sales Channels (`/settings/sales-channels`), and Channel Partner Preferences (`/channel-partners`).

---

## 💾 9. Database Backup & Schema Mismatch Synchronization Strategy

- **Format & Retention**: System database backups are generated as executable `.sql` dump files containing `DROP TABLE IF EXISTS` statements, `SHOW CREATE TABLE` DDL structures, and column-explicit batch `INSERT INTO` statements. The system automatically retains only the 5 most recent backup files.
- **Handling Mismatches Between Backup Schema & Present Schema**:
  1. **Explicit Column Names (`INSERT INTO \`table\` (\`col1\`, \`col2\`)`)**: Prevents column count crashes. New columns in the active DB automatically default to their defined `DEFAULT` values (e.g. `is_active=1`, `created_at=NOW()`).
  2. **Automated Idempotent Post-Restore Migration (`db_migrate.py`)**: Immediately after importing/restoring a `.sql` backup, `db_migrate.py` must be executed to run `add_column_safely()`, adding any missing tables or columns required by the active application code.
  3. **Foreign Key Safety**: Backups wrap imports inside `SET FOREIGN_KEY_CHECKS=0;` and `SET FOREIGN_KEY_CHECKS=1;` to prevent foreign key constraint ordering deadlocks.
  4. **Header Version Verification**: `.sql` headers contain software version and timestamp metadata for schema version tracking.

---

## 🛠️ Common Operations & Developer Commands

### Run Development Server
```bash
PYTHONPATH=. ./venv/bin/python run.py
```

### Apply Database Migrations
```bash
PYTHONPATH=. ./venv/bin/python db_migrate.py
```

### Verify Application Health
```bash
curl -I http://127.0.0.1:8090/login
```

---

## ⚠️ Common Pitfalls & Checklist
1. **Never alter L1-L4 Position reporting rules**: L1 must report to L2, L2 to L3, L3 to L4.
2. **Always run `db_migrate.py` after model changes**: Custom schema migrations are handled safely via `add_column_safely()`.
3. **Use PTR label everywhere**: Ensure `PTR` is displayed instead of `Unit Cost` in product listing and stock reports.
4. **Enforce Glassmorphic Alerts**: JavaScript alerts must use the custom modal design system (`confirmSubmit` / custom modal alerts).
5. **Territory Manager Scope Rules**: Territory Managers can create/edit L1 Positions, create/edit Channel Partners, create/edit Beats & Routes, create/edit Vendors, and perform inventory inwarding/adjustments for regional warehouses. On the Geography screen, they see ONLY their assigned Region and child Territories under their Region. They CANNOT create or edit Users, Geographies, Warehouses, Products, or L2-L4 Positions.
6. **Inventory Stock Deactivation Validation**: Deactivating any Product, Warehouse, or Region must validate that active inventory stock is 0. If inventory stock is present, deactivation is rejected with a clear validation error.
7. **No Hardcoded Test Warehouses**: Warehouses must never be hardcoded or auto-seeded in migration scripts (`db_migrate.py`) or setting routers. All warehouses must be explicitly configured via Admin controls.
8. **Channel Partner Mandatory Fields**: Channel Partners require mandatory selection of at least 1 Sales Channel (Multi-select) and a Geography Scope limited to Territory or Region.
9. **SQL Database Backups & 5-File Retention Policy**: System database backups are generated in standard executable `.sql` format. The system automatically retains only the 5 most recent backup files, purging older files upon new backup creation.
10. **Post-Restore Schema Synchronization**: Always run `db_migrate.py` after restoring any `.sql` backup to align the schema with the latest application models via `add_column_safely()`.
11. **First Bootup Onboarding & Encrypted Admin Password**: Admin credentials are no longer served from `.env`. On first bootup, the system presents an Onboarding Wizard (`/onboarding`) to configure Admin credentials (saved as bcrypt hash in `users` table) and optionally restore data from a `.sql` backup.
12. **Sidebar Hierarchy**: Always maintain standard sidebar order (`Dashboard` → `Field Tracking` → `Operations` → `Analytics` → `Catalogue` → `Master Data` → `Configuration` → `Developer`).
13. **User Management Form Rules**: Company Profile field is removed; Assigned Positions hierarchy features real-time search filtering; `is_active` checkbox is removed from the Edit form and managed strictly via User List action buttons (`Deactivate` / `Activate`).
