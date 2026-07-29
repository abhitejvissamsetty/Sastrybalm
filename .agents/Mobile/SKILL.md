---
name: safar-mobile
description: >-
  Safar Mobile App technical guide and troubleshooting documentation.
  Covers Flutter, Riverpod, GoRouter, Hive offline storage, Geolocator GPS,
  shadcn minimalist monochrome UI design system, 5-persona role-based workflows (Field Reps, TM Territory, TM Region, QC Manager, Vendor Admin/Tech),
  attendance check-in/out, Timesheets sync, Expenses & Receipts, Joint Working, Leave Application, EIS/MIS dashboards, Procurement Workflows, Camera/Gallery integration, IST timezone handling, and runtime error fixes.
---

# Safar Mobile App — Architecture, Design System & Role-Based Workflows Guide

## Overview
The Safar Mobile App is built with **Flutter 3.x**, **Riverpod 2.x**, **GoRouter 13.x**, **Dio 5.x**, **Hive (Encrypted)**, and **Geolocator**. It provides field sales representatives, territory managers, QC managers, and vendor technicians with a professional, high-contrast monochrome **shadcn UI** minimalist interface, beat plan route management, order booking, payment collections, joint working, leave management, EIS/MIS dashboards, procurement workflows, timesheet logs, and offline sync capabilities.

---

## 👥 Persona Workflow Specifications

### 1. Field Reps (L1 Role)
- **Log In & Shift**: Start Day (`/attendance/checkin`), End Day (`/attendance/checkout`), Log Out.
  - Clicking **Begin Workday** triggers the **1. Begin Workday Shift** modal bottom sheet with **Start Shift Now** button.
  - Workday Lock Policy: Outlet visits and order entries are locked until shift is active.
- **Expenses & Timesheets**: 
  - Submit Expenses (`/expense`) with optional camera/gallery receipt proof (`POST /api/v1/expenses`).
  - View live synced Timesheets (`/timesheet`) fetched via `GET /api/v1/timesheets/my-timesheets`.
- **Start Retailing**:
  - Select Beat from assigned positions (`/beats/my`), Select Outlets, Add Outlet.
  - **View Outlet & Mandatory Check**: Evaluates `image_url`, `mobile`, `name`, `address`, and `gps`. If any of these 5 fields are missing, `is_incomplete=true` triggers auto-redirect to **Edit Outlet Flow**.
  - **Edit Outlet**: Submits changes via `POST /outlets/{id}/edit-request` for Approval Flow.
  - **Submit Outlet Outcomes**: Secondary Orders (`order_type="secondary"`), Payments, Asset Capitalizations, Material Requests, and Asset Maintenance Logs.
  - **Map View**: View Outlets associated with Beat in Map View.
- **Apply for Leave**: Submit Leave Applications (`POST /leaves`, `GET /leaves/my-leaves`). Hidden for Vendor Admin and Vendor Technician roles across all app screens.
- **Journey Plan**: View personal route and scheduled visits (`GET /journey-plan`).
- **EIS (Employee Information System)**: Personal stats (Secondary Orders, Payments, Assets, MR Statuses, Attendance Days, Working Hours, Productivity KPIs).

### 6. Start Retailing, Quick Actions Structure & Beat Route View
- **Role-Based Access Rules**:
  - **Start Retailing**: Available for both L1 Users (Field Reps) and L2/L3/L4 Users (Territory Managers, Regional Managers, Admins).
  - **Card Design System & Shift State Color Inversion**:
  - **Workday Hero Card (Dynamic Color Inversion on Shift Check-In)**:
    - **Before Starting Shift (`isCheckedIn == false`)**: Rendered in **Light White (`#FFFFFF`)** with `#E4E4E7` border, black title (*Ready to Start Your Shift?*), grey subtitle, and **Black Pill Button (`Begin Workday`)**.
    - **After Starting Shift (`isCheckedIn == true` / Shift In Progress)**: Colors dynamically **INVERT into Dark Zinc (`#09090B`)** with `#27272A` border, white title (*Shift In Progress*), green status dot, and **White Pill Button (`End Workday`)**.
  - **White Background / Black Text Cards (Always `isDark: false`)**:
    - **Create Primary Card**: Full-width **White Card (`#FFFFFF`)** with `#E4E4E7` border, black title, grey description, and dark button (*Create Primary Order Now*).
    - **Apply Leave Card**: Full-width **White Card (`#FFFFFF`)** with `#E4E4E7` border, black title, and grey subtitle.
  - **Dynamic Inversion Action Tiles**:
    - **Start Retailing** & **Joint Working**:
      - **Before Starting Shift (`isCheckedIn == false`)**: Rendered in **Light White (`#FFFFFF`)** with `#E4E4E7` borders, dark icons `#09090B`, and dark text.
      - **After Starting Shift (`isCheckedIn == true`)**: Colors dynamically **INVERT to Dark Zinc (`#09090B`)** with `#27272A` borders, white text, and white icons on `#18181B` containers.
- **Quick Actions Layout Hierarchy**:
    - Row 1 (Side-by-side): `Start Retailing` | `Joint Working`
    - Row 2 (Full Width Card): `Create Primary`
    - Row 3 (Full Width Card): `Apply Leave` (hidden for `vendor_admin` & `vendor_technician`)
  - **L1 Quick Actions Structure**:
    - 2-Column Grid: `Start Retailing` | `Apply Leave` (No `Create Primary` or `Joint Working`)
  - **App Drawer (Modal Bottom Sheet)**:
  - Tapping **Start Retailing** slides up an interactive App Drawer (`isScrollControlled: true`, `enableDrag: true`).
  - Dismissible via out-focusing (backdrop tap) or throwing down swipe.
  - Includes a top **Search Bar** to filter available beats dynamically by beat name, beat code, L1 position name, or assigned user.
  - **Dynamic API Filter-Based Hierarchy Resolution (No Hardcoding)**: `resolve_user_hierarchy_beats` evaluates position hierarchy relationships dynamically via SQL/ORM (`user_positions` → `positions` → `direct_reports` → `position_beats`). No beat names, codes, or IDs are hardcoded for inclusion or exclusion in any way; beats outside the authenticated user's position tree (such as `LAALPAHAD` under Odisha) or unassigned beats are naturally excluded by dynamic database query filtering.
  - Displays full-width beat cards with:
    - Beat Name & Beat Code badge.
    - **Info under Beat Title**:
      - `Position: [L1 Position Name / Code]` (`l1PositionName`)
      - `Assigned User: [User Full Name]` (`assignedUserName`)
    - Active Outlets count badge & selection chevron arrow.
- **Beat Page (Outlets View - `/beat`)**:
  - Placed **outside `ShellRoute`** in `app.dart` so it renders full-screen **without the bottom footer menu**.
  - Shows all active outlets in full-width cards displaying:
    - Outlet Name & Outlet Code / ID tag (`OUT-xxxx`).
    - **Phone Number** (`outlet.mobile`, with phone icon `Icons.phone_rounded`).
    - Owner Name, Address, Channel badge, and distance.
  - **Dual Action Controls**:
    - 🔍 **Search FAB**: Toggles inline search bar to search outlets by name, code, phone, or owner.
    - 📍 **New Outlet FAB**: Navigates to a dedicated full-screen page (`/outlet/new`, `OutletCreateScreen`) to register a new customer shop with complete form validation, beat assignment, and GPS tag capture.

### 2. Territory Managers (Geography = Territory)
- **Log In & Shift**: Start Day, End Day, Log Out.
- **Expenses & Timesheets**: Submit Expenses with receipt photos, view synced Timesheets.
- **Start Retailing**:
  - Select Beat from `L1 Position` assigned to User (`GET /beats/l1-positions`), Select Outlets, Add Outlet.
  - **View Outlet & Mandatory Check**: Auto-triggers Edit Flow if mandatory fields are missing.
  - **Edit Outlet**: Edit Outlet with Approvals Flow.
  - **Submit Outlet Outcomes**: Visits (`No Order Reason` or `Order & Payment`), Assets (`Installation` & `Maintenance Log`), Material Requests.
  - **Map View**: View Outlets in Map View.
- **Joint Working**:
  - Select Subordinate User (`GET /subordinates`) → `L1 Position` & Beat (`GET /subordinates/{id}/beats`) → Outlets.
  - No `Add Outlet` button in Joint Working mode. `Edit Outlet` triggers Approval Flow.
  - **Submit Joint Outcomes**: Visits (`Notes`), Assets (`Installation` / `Maintenance`), Material Requests.
  - View Outlets in Map View.
- **Primary Order**: Select Channel Partner and place Primary Order (`POST /orders` with `order_type="primary"`).
- **Apply for Leave & Journey Plan**: Apply Leave, View Journey Plan for self & team L1 users.
- **EIS & MIS Dashboards**: View personal EIS stats & Managerial Information System (MIS) team operational outcomes.

### 3. Territory Managers (Geography >= Region)
- **Log In & Shift**: Start Day, End Day, Log Out.
- **Expenses & Timesheets**: Submit Expenses, Submit Timesheets.
- **Procurement Workflows**: Shortlist Vendor for Material Requests, approve Supplier Quotations (`POST /procurement/quotations/{id}/approve`), auto-generating Work Orders.
- **Joint Working**: Select Subordinate User → `L1 Position` & Beat → Outlets.
- **Apply for Leave & Journey Plan**: Apply Leave, View Journey Plan.
- **EIS & MIS Dashboards**: View personal EIS stats & MIS team outcomes.

### 4. QC Managers (`qc_manager`)
- **QC Inspection Portal (`/procurement/qc`)**:
  - View Work Orders in `QC Pending` status.
  - Verify final dimensions, material specifications, and manufactured photos.
  - Allocate unique Batch IDs (`BATCH-YYYYMMDD-XXXX`) and generate `ProcurementItem` records (`status="pending_installation"`).

### 5. Vendor Admins & Technicians (`vendor_admin` / `vendor_technician`)
- **Vendor Admin Portal (`/procurement/vendor-admin`)**:
  - Submit Supplier Quotations with side-by-side Recce vs Original MR comparison.
  - Change Work Order status to `QC Pending` with manufactured proof photos.
- **Vendor Tech Portal (`/procurement/vendor-tech`)**:
  - On-site Recce submission (dimensions, specs, client notes, site photo).
  - Convert verified `ProcurementItem` to `AssetCapitalization` upon physical installation.
  - Submit Asset Maintenance Logs (`POST /procurement/assets/{id}/maintenance-logs`).

---

## 🧭 Navigation Layout Structure

The app features a bottom navigation bar (`HomeScreen`):
- **Tab 1: Home (`/home`, `Icons.home_rounded`)**: Executive Header, Dark Zinc Hero Shift Card (`Begin Workday` / `Apply Leave`), and Workday Action Center.
- **Tab 2: Expenses (`/expense`, `Icons.receipt_long_rounded`)**: Dual tab for logging expense claims and viewing live synced reimbursement history.
- **Tab 3: Timesheets (`/timesheet`, `Icons.access_time_filled_rounded`)**: Real-time shift check-in logs, working hours, total customer visits, and approved timesheets.
- **Tab 4: Analytics (`/analytics/eis-mis`, `Icons.bar_chart_rounded`)**: Dual tab for self EIS performance and managerial MIS team metrics.

---

## 📸 Camera & Photo Library Integration

- **Permissions**:
  - **iOS (`Info.plist`)**: Includes `NSCameraUsageDescription` and `NSPhotoLibraryUsageDescription`.
  - **Android (`AndroidManifest.xml`)**: Includes `CAMERA` and `READ_MEDIA_IMAGES`.
- **Unified Picker (`ImagePickerService`)**:
  - Provides `showImageSourceDialog(context)` bottom sheet modal allowing user to choose between **Take Photo with Camera** (`ImageSource.camera`) and **Choose from Gallery** (`ImageSource.gallery`).
  - Automatic resolution scaling (`1280px` max, `85%` quality) for mobile uploads.

---

## ⏰ Timezone & DateTime Handling (IST GMT+5:30)

- **Backend**: Generates naive IST datetimes (`datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)`), returning ISO strings such as `2026-07-27T19:18:00`.
- **Mobile Parsing (`DateFormatter.parseDateTime`)**: Parses naive IST strings without appending `'Z'` (which previously caused incorrect UTC offset shifts). Formats display times accurately in local IST (e.g. `07:18 PM`).

---

## 🎨 Shadcn Minimalist Design System

### 1. Color Palette (Zinc / Neutral Tokens)
- **Background**: `#FAFAFA` (Zinc 50 Light) / `#09090B` (Zinc 950 Dark)
- **Surface / Cards**: `#FFFFFF` (Pure White) / `#18181B` (Zinc 900)
- **Primary / Actions**: `#09090B` (Zinc 950 Black) / `#FAFAFA` (Zinc 50 White)
- **Secondary / Containers**: `#F4F4F5` (Zinc 100) / `#27272A` (Zinc 800)
- **Borders**: `#E4E4E7` (Zinc 200) / `#27272A` (Zinc 800) 1.0px width
- **Text Primary**: `#09090B` (Zinc 950) / `#FAFAFA` (Zinc 50)
- **Text Secondary**: `#71717A` (Zinc 500) / `#A1A1AA` (Zinc 400)

---

## 🏛️ Architecture & Core Components

### 1. State Management & Navigation
- **Riverpod Providers**:
  - `authStateProvider`: Manages `AsyncValue<AppUser?>` authentication state.
  - `attendanceProvider`: Manages `AsyncValue<AttendanceState>`.
  - `myTimesheetsProvider`: Fetches user's live timesheet logs.
  - `myExpensesProvider`: Fetches user's live expense claims.
  - `syncProvider`: Tracks pending offline queue count.
  - `appConfigProvider`: Holds dynamic app configurations.
- **GoRouter Configuration**:
  - Defined in `lib/app.dart`.
  - Routes: `/home`, `/beat`, `/history`, `/order/new`, `/order/:id`, `/outlet/:id`, `/payment/collect`, `/expense`, `/material-request`, `/asset-cap`, `/leave/apply`, `/timesheet`, `/analytics/eis-mis`, `/joint-working`, `/procurement/qc`, `/procurement/vendor-admin`, `/procurement/vendor-tech`.

---

## 🤖 Android Configuration & Network Rules

1. **Network Base URL Loopback (`ApiConfig`)**:
   - On Android Emulator, `127.0.0.1` refers to the Android device loopback interface. `ApiConfig.baseUrl` dynamically uses `Platform.isAndroid ? 'http://10.0.2.2:8090/api/v1/' : 'http://127.0.0.1:8090/api/v1/'` to reach host machine services on port 8090.
   - For physical Android testing on local WiFi, update `ApiConfig.baseUrl` to your Mac's LAN IP (e.g. `http://192.168.x.x:8090/api/v1/`).

2. **Cleartext HTTP Traffic**:
   - `AndroidManifest.xml` has `android:usesCleartextTraffic="true"` enabled so non-HTTPS local development URLs function without HTTP block errors.

3. **Required Android Permissions (`AndroidManifest.xml`)**:
   - `INTERNET`
   - `ACCESS_FINE_LOCATION` & `ACCESS_COARSE_LOCATION`
   - `CAMERA`
   - `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE` (maxSdkVersion 32), and `READ_MEDIA_IMAGES`

---

## 📱 7. Enhanced Mobile Workflows: Start Retailing, Create Primary & Joint Working

### A. Start Retailing Workflow & Order Entry
1. **Outlet Discovery & Visit Initiation**:
   - Outlets viewable in **List / Map View** under active Beat.
   - Select Outlet → Outlet Detail View → Footer Action Button (**Begin Visit**).
   - Initiate Visit against Outlet (`visit_id` created) → Navigation to **Order View** or **No Order Reason View**.
2. **Order View Specifications**:
   - **Product Catalog Filtering**: Display items where `category_scope == 'Sale'`.
   - **L3 Warehouse Resolution for Stockable Items**:
     - If product has `is_stockable_item == 1`, fetch resolved warehouse from the user's **L3 Position hierarchy** (`Outlet → Beat → L1 Position → L2 Position → L3 Position → L3 User → geography → warehouse`).
     - Map resolved warehouse to the Order's `warehouse_id`.
   - **Custom Numeric On-Screen Keyboard (OSK)**:
     - Embedded numeric OSK (digits 0-9, backspace/delete, and **Next** button) to enter line item quantities.
     - Live calculation of **Order Line Amount** and grand total.
   - **Fulfillment & Stockable Validation Step**:
     - Tapping **Next** on OSK transitions to the Fulfillment Step.
     - Options: `['Channel Partner', 'Company Order']`.
     - **Validation & Disabled State**: If ANY selected product in the order has `is_stockable_item == 0`, grey out **'Company Order'** and display warning banner: *"Product is not available to be sold in warehouse L3 User"*.
     - **Channel Partner Selection**: Directly submits the order.
     - **Company Order Selection (`is_company_order = 1`)**: Directs to Payment Details Page.
3. **Embedded Payment Collection Page**:
   - Offers **Credit Order** vs **Paid Order** (`Full` / `Partial`).
   - If **Credit Order**: sets `is_paid = 0`, `payment_type = 'Credit'`.
   - If **Paid Order**: sets `is_paid = 1`, requiring selection of `payment_type` (`Full`, `Partial`), `payment_mode` (`Cash`, `UPI`, `NEFT/RTGS`, `Others`), and `payment_reference`.

### B. Create Primary Order Workflow (Mobile & Backend Logic)
- **Target Selection**: Raised against a **Channel Partner** (instead of an Outlet).
- **Location & Visit Handling**: Requires **Address Details**, does **NOT** capture GPS coordinates or create a Visit Record (`visit_id = null`).
- **Database & UI Mapping**: Uses unified `party_id` with `party_type = 'Channel Partner'`.
- **Payment Defaults**: Defaults to `is_company_order = 1`, `is_paid = 0` (unless paid order is selected).

### C. Joint Working Workflow
- **Bottom Drawer Transition**: Sliding modal bottom sheet drawer for selecting manager hierarchy.
- **Subordinate Position & Beat Selection**:
  - Territory Managers (Positions `L2`, `L3`, `L4`) select an **L1 Position** under their direct reporting hierarchy (includes inline search filter).
  - List displays assigned user name per position; unassigned positions are hidden.
  - Select Beat under the selected L1 Position.
- **Outlet View & Visit Execution**:
  - Displays Outlets under Beat in List/Map View (**without** New Outlet FAB).
  - Select Outlet → Outlet Detail View → Footer Action Button (**Begin Visit**) → Initiate Visit.
- **Joint Visit Outcomes**:
  1. **No Order Reason** or **Visit Notes**.
  2. **Triple-Scoped Order Placement Link**: Select Order ID from today's orders punched by L1 users. Includes **"Fetch Orders Today"** action button passing `outlet_id`, `beat_id`, and `subordinate_user_id` query parameters for strict Outlet, Beat, and Position Hierarchy scoping.
  3. **Photo Evidence Upload**: Capture and upload store visit photo.

---

## 🧪 Testing Verification
Run mobile Flutter unit and widget tests:
```bash
cd mobile
flutter test
```

### Completion Verification — 2026-07-28
- Start Retailing passes the active Visit ID, displays resolved L3 warehouse stock, persists No Order Reason, and server-validates Company Order availability/payment state.
- Create Primary persists Channel Partner Party and delivery address without Visit/GPS and uses Sales-scope, warehouse-stock-aware product entry.
- Joint Working is reporting-tree scoped for L2/L3/L4 managers and persists selected L1 user, notes, No Order Reason, linked same-day Order, device GPS, and multipart photo evidence.
- Leave duration/session are persisted fields; approval lists and actions are reporting-tree scoped.
- Canonical local mobile API is Nginx port `8080`.
- Verified with Python compile, Flutter analyzer (no compile errors), Docker health/migrations, MySQL schema inspection, and live OpenAPI assertions.

## 📦 Outlet Home: Material Requests and Assets (2026-07-28)

- `OutletDetailScreen` provides **New MR** and an **Assets** bottom sheet containing **Asset List** and **New Asset**.
- Navigation is outlet-scoped and does not rely only on `selectedOutletProvider`.
- `MrScreen(outletId)` loads the latest outlet summary and active `Marketing - Procurement` Products from the server. It enforces one Product, a worded description, optional positive L/W/H/D values, and three required camera/gallery images.
- `AssetCapitalizationScreen(outletId)` displays the server-resolved L3 warehouse and only its in-stock `Marketing - Stock` Products. Item and warehouse free-text inputs were removed.
- `AssetListScreen(outletId)` displays existing outlet deployments and links to New Asset.
- `MaterialRequestService` and `AssetCapitalizationService` use Dio multipart requests for images and typed outlet-scoped context/list endpoints.
- Flutter analyzer reports no compilation errors. Existing repository lint and Flutter deprecation diagnostics remain non-blocking.

## 🏭 Role-Based Procurement Portals (2026-07-28)

### Vendor Technician
- Four tabs: Recce, Ready Items, Assets, Maintenance.
- Assigned MR and Ready Item records are Vendor-scoped and support List/Map display.
- Recce captures actual camera/gallery evidence (exactly two images) through the procurement upload endpoint.
- Ready Item installation uploads evidence and creates one linked Asset.
- Technician creates Maintenance Logs and reports percentage progress with optional image evidence.

### Vendor Admin
- Four tabs: MRs, Work Orders, Assets, Maintenance; assigned MRs support List/Map display.
- Quotation action is available only after approved Recce and submits the non-GST base amount; GST is calculated by the server from Product configuration.
- Assigned Work Orders can be acknowledged; acknowledged work reports progress and transitions to QC Pending at 100%.
- Maintenance supports progress and image evidence.

### QC Manager
- Tabs: Work Orders, Assets, Maintenance.
- QC Pending Work Orders support Return (progress below 100 plus mandatory remark) and two-image QC Report completion.
- Completed Work Orders support Recall for QC with server-side Item invalidation safeguards.
- QC may create Maintenance Logs and validate only 100%-Completed logs.

### Shared service
- `ProcurementService` centralizes scoped lists, image uploads, state transitions, Item deployment, and Maintenance commands.
- `ProcurementMap` renders role-scoped Outlet coordinates over OpenStreetMap without loading full entity detail.
