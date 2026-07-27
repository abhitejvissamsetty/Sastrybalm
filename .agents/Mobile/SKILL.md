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
- **Apply for Leave**: Submit Leave Applications (`POST /leaves`, `GET /leaves/my-leaves`).
- **Journey Plan**: View personal route and scheduled visits (`GET /journey-plan`).
- **EIS (Employee Information System)**: Personal stats (Secondary Orders, Payments, Assets, MR Statuses, Attendance Days, Working Hours, Productivity KPIs).

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

## 🧪 Testing Verification
Run mobile Flutter unit and widget tests:
```bash
cd mobile
flutter test
```
