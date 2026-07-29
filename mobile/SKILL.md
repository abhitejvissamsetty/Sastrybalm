# Safar SFA Mobile Application — Developer & Operations Skill Guide

Comprehensive technical documentation and operational log for the Safar SFA Flutter Mobile Application.

---

## 1. System Overview & Architecture

- **Framework**: Flutter 3.19+ (Dart 3.3+)
- **State Management**: Riverpod (`flutter_riverpod: ^2.5.1`)
- **HTTP Client**: Dio (`dio: ^5.4.3+1`) with JWT bearer token interceptors & auto-refresh
- **Secure Storage**: `flutter_secure_storage` for encrypted JWT storage
- **Navigation**: `go_router: ^13.2.1` with `ShellRoute` & standalone route guards
- **Map & Location**: Live OpenStreetMap tile layer (`flutter_map: ^6.1.0`, `latlong2: ^0.9.0`), `geolocator: ^11.0.0`, `url_launcher: ^6.2.5` for Google Maps redirection

---

## 2. API & Server Environment Configuration

- **Development Port Configuration** ([`mobile/lib/config/api_config.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/config/api_config.dart)):
  - **Android Emulator**: `http://10.0.2.2:8080/api/v1/`
  - **iOS Simulator / macOS**: `http://127.0.0.1:8080/api/v1/`
- **Reverse Proxy & Direct Ports**: Nginx container maps host port `8080:80` and FastAPI container maps `8090:8090`.

---

## 3. Detailed Change Log & Features Delivered

### 🔐 1. Passwordless OTP Authentication Fix
- **Issue Resolved**: 500 error on mobile sign-in for registered accounts (`kkalpanamuthu10@gmail.com`).
- **Fix**:
  - Restored baseline database backup [`safar_sfa_backup_20260728_104243.sql`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/safar_sfa_backup_20260728_104243.sql) into Docker MySQL container `safar-db`.
  - Added missing `order.py` import to [`app/models/__init__.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/models/__init__.py).
  - Updated `ApiConfig.baseUrl` port to `8080`.
- **Status**: Verified `HTTP 200 OK` on `/api/v1/auth/request-otp` and `/api/v1/auth/verify-otp`.

---

### 🗺️ 2. Beat & Position Persistence
- **Issue Resolved**: Unpersisted position-to-beat assignments across Docker restarts.
- **Fix**:
  - Mapped `OMR ECR` (Beat ID `1`) to `SOUTH CHN L1` (Position ID `4`).
  - Saved and dumped updated MySQL state into host backup file `safar_sfa_backup_20260728_104243.sql`.

---

### 📱 3. Mobile Footer Navigation (List View vs Map View)
- **Files Modified**:
  - [`mobile/lib/screens/beat/beat_plan_screen.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/screens/beat/beat_plan_screen.dart)
  - [`mobile/lib/screens/joint_working/joint_working_screen.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/screens/joint_working/joint_working_screen.dart)
  - [`mobile/lib/app.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/app.dart)
- **Features Implemented**:
  - Replaced global bottom shell navigation on Beat Outlet views with a dedicated 2-tab footer:
    - **List View** (`Icons.view_list_rounded`)
    - **Map View** (`Icons.map_rounded`)
  - Floating Action Buttons (`FAB`) displayed in **List View**:
    - **Search FAB**: Toggles live search input.
    - **+ New Outlet FAB**: Navigates to `/outlet/new`.

---

### 📍 4. Interactive OpenStreetMap Canvas & Google Maps Redirection
- **Database Provisioning**:
  - Seeded 5 active Chennai OMR/ECR outlets (`OMR Hypermarket`, `ECR Bayview Traders`, `Sholinganallur General Store`, `Navalur Central Mart`, `Palavakkam Daily Needs`) with GPS coordinates (`gps_lat`, `gps_lng`) in MySQL.
- **OpenStreetMap Canvas**:
  - Integrated `flutter_map` with OpenStreetMap tile provider `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
  - Interactive outlet pins displaying outlet name tags and active state indicators over real geographical coordinates.
- **Google Maps Integration**:
  - Tapping any outlet pin or clicking the **"Google Maps"** button launches external Google Maps application at `https://www.google.com/maps/search/?api=1&query={lat},{lng}` via `url_launcher`.

---

### 🏖️ 5. Single-Day Leave Application & Hierarchical L1-L4 Approval Logic
- **Mobile Single-Day Picker**:
  - Replaced the date-range picker with a single **Leave Date** picker in [`mobile/lib/screens/leave/leave_apply_screen.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/screens/leave/leave_apply_screen.dart).
  - Added **Full Day** / **Half Day** duration selector toggle cards and half-day session dropdown (First Half / Second Half).
- **Hierarchical Approval Rules** ([`app/models/user.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/models/user.py)):
  - **L1 & L2 Leaves**: Can be approved/rejected by **L3** or **L4** users (and System Admin).
  - **L3 Leaves**: Can **ONLY** be approved/rejected by **L4** users (and System Admin).
  - **L1 & L2 Users**: Cannot approve any leaves.
  - **L3 Users**: Cannot approve L3 or L4 leaves.
- **Web Admin Portal Integration**:
  - Updated Web Admin Leave Management router ([`app/routers/admin_leaves.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/routers/admin_leaves.py)) and HTML Dashboard template ([`app/templates/leaves/index.html`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/templates/leaves/index.html)).
  - Enforces `user.can_approve_leave_for(applicant)` checks on both backend API calls and frontend UI rendering.

---

### 🛑 6. Strict Back-Button Session Cache Prevention (Web & Mobile)
- **Problem**: When a user logged out on Web or Mobile and pressed the browser/device back button, the previous session/pages were rendered from cache or history.
- **Web Solution**:
  - Added `prevent_browser_caching_middleware` in [`app/main.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/main.py) and anti-cache headers in [`app/routers/auth.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/app/routers/auth.py):
    `Cache-Control: no-cache, no-store, must-revalidate, max-age=0, private`
  - Forces browsers to reject bfcache (back-forward cache) and send fresh requests, triggering server 302 redirects to `/login`.
- **Mobile Solution**:
  - Wrapped `LoginScreen` in `PopScope(canPop: false)` in [`mobile/lib/screens/auth/login_screen.dart`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/mobile/lib/screens/auth/login_screen.dart).
  - Pressing the back button on the Login screen immediately exits the application (`SystemNavigator.pop()`) instead of popping back into logged-out routes.

---

### 🧹 7. Demo Data Seeding Removal & Database Reset Utility
- **Disabled Automatic Seeding**:
  - Disabled automatic demo product seeding functions (`seed_products()`) in [`exclude_from_deployment/create_db.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/exclude_from_deployment/create_db.py).
  - Verified Docker container startup (`entrypoint.sh`) only performs database schema migrations (`db_migrate.py`), not dummy data generation.
- **Data Cleanup Utility**:
  - Created [`clear_demo_data.py`](file:///Users/johnwesleygovada/Desktop/Sastrybalm/clear_demo_data.py) script.
  - Wiped all transactional tables (`orders`, `order_items`, `payments`, `payment_submissions`, `expenses`, `leaves`, `material_requests`, `timesheets`, `asset_capitalizations`, `alerts`, `stock_movements`, `vendor_quotations`, `work_orders`).

---

## 4. Key Verification & Development Commands

```bash
# 1. Run Flutter Mobile App on iOS Simulator
cd mobile
flutter run -d E07BEBC8-B001-4DFA-97D4-12E95FAB9C4D

# 2. Analyze Code Quality & Static Types
flutter analyze

# 3. Clear All Demo/Test Transactional Data
docker exec -i safar-app python - < clear_demo_data.py

# 4. Dump Persistent MySQL Database
docker exec safar-db mysqldump -u root -prootpassword safar_db > safar_sfa_backup_20260728_104243.sql
```

---

## 5. Verified Retailing Completion (2026-07-28)

### Start Retailing
- Beat Outlets support list/map discovery, search, Outlet detail, Visit check-in/timer, Order entry, and persisted No Order Reason completion.
- Secondary Order passes the exact active Visit ID, resolved warehouse, Outlet Party, and Beat.
- Sales-scope products display resolved L3 warehouse stock. Numeric OSK provides digits, delete, and Next-to-Fulfilment with live totals.
- Company Order is disabled for non-stockable or insufficient-stock selections. Channel Partner submits directly; Company fulfilment enforces Credit or Paid (Full/Partial) details.

### Create Primary
- Selects a Channel Partner Party, persists structured delivery address, uses no Visit/GPS, and submits a Credit Company Order.
- Product entry is Sales-scope and warehouse-stock aware.

### Joint Working and Leave
- L2/L3/L4 managers search assigned L1 Position/user entries only within their reporting tree, then select Beat and Outlet.
- Outcomes persist notes, No Order Reason, hierarchy-scoped same-day L1 Order, actual device GPS, and camera/gallery evidence through multipart upload.
- Leave duration/session are explicit API/database fields; approval visibility and actions are reporting-tree scoped.

### Runtime Verification
- Canonical local mobile API is Nginx port `8080` (`10.0.2.2` Android emulator; `127.0.0.1` iOS/macOS).
- Flutter analyzer completes without compilation errors; remaining diagnostics are unrelated lint/deprecation warnings.

---

## 6. Outlet Home Material Request and Asset Workflows

### Navigation
- `/outlet/:id/material-requests/new` opens a new MR for the explicit Outlet.
- `/outlet/:id/assets` lists that Outlet's deployed assets.
- `/outlet/:id/assets/new` deploys a new marketing-stock asset.
- Outlet Detail shows **New MR** and an **Assets** action sheet with List/New choices.

### New Material Request
- Loads `GET /outlets/{id}/material-request-context`.
- Product is a required single selection restricted server-side to `Marketing - Procurement`.
- Captures Description, optional positive Length/Width/Height/Depth in centimetres, and required Present Outlet, Installation Place, and Customer Approval Letter images.
- Submits multipart data to `POST /material-requests`.

### New Asset
- Loads `GET /outlets/{id}/asset-products`.
- Shows the L3-resolved warehouse read-only and lists only active `Marketing - Stock` products having positive stock in that warehouse.
- Captures Product, positive Quantity, optional notes, and optional deployment image.
- Server atomically deducts warehouse stock and creates an outward stock movement.

### Asset List
- Loads `GET /outlets/{id}/assets`.
- Shows asset number, product/item, source warehouse, and deployed quantity.

### Verification
- Dart formatting completed and Flutter analyzer has no compilation errors.
- Backend migration, live OpenAPI paths, and healthy Docker startup were verified on 2026-07-28.

---

## 7. Procurement Role Portals

- Vendor Technician route `/procurement/vendor-tech`: assigned Recce List/Map, Ready Item List/Map, Asset installation, Asset maintenance, progress images.
- Vendor Admin route `/procurement/vendor-admin`: assigned MR List/Map, approved-Recce quotation, Work Order acknowledgement/progress, Assets and Maintenance.
- QC Manager route `/procurement/qc`: QC Pending/Completed Work Orders, QC report/return/recall, Assets, Maintenance creation and completion validation.
- All evidence uses camera/gallery selection and `POST /procurement/attachments/upload`; typed entity attachment records are created during Recce, QC and progress commands.
- Portal lists are Vendor/QC-assignment scoped by the backend. Hiding a tab is never treated as authorization.
- Work Order progress and Maintenance progress are append-only history records; UI refreshes after each accepted state transition.
