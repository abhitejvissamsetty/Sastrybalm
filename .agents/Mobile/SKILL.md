---
name: safar-mobile
description: >-
  Safar Mobile App technical guide and troubleshooting documentation.
  Covers Flutter, Riverpod, GoRouter, Hive offline storage, Geolocator GPS,
  shadcn minimalist monochrome UI design system, attendance check-in/out workflows,
  restricted module scoping, payment collection, beat routes, and runtime error fixes.
---

# Safar Mobile App — Architecture, Design System & Troubleshooting Guide

## Overview
The Safar Mobile App is built with **Flutter 3.x**, **Riverpod 2.x**, **GoRouter 13.x**, **Dio 5.x**, **Hive (Encrypted)**, and **Geolocator**. It provides field sales representatives and territory managers with a professional, high-contrast monochrome **shadcn UI** minimalist interface, beat plan route management, order booking, payment collections, and offline sync capabilities.

Key Features:
- **Shadcn Minimalist Monochrome UI**: High-contrast Zinc/Neutral color system, clean 1px borders, subtle 10-14px radii, and refined typography.
- **Executive Dashboard**: Workday shift check-in / check-out status, minimalist GPS status badge, quick operational actions, and overview metrics.
- **Beat Plan & Outlets**: Route planning, outlet visits, and distance-based GPS tracking.
- **Orders & History**: Order creation with PTR pricing and GST calculations, sync status tracking.
- **Payment Collection & Submissions**: Cash and UPI collections, denomination validation, offline submission queuing.
- **Restricted Module Scoping**: Access control for Expenses, Timesheets, and Material Requests based on user roles and geography levels.
- **Offline Sync Engine**: Encrypted Hive queue (`pending_ops`) that auto-syncs when network connectivity is restored.

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

### 2. Component Guidelines
- **Hero Shift Card**: Solid `#09090B` dark zinc card with `#27272A` border, clean status pill, and high-contrast white action button.
- **Bottom Navigation**: Floating rounded card with `#FFFFFF` surface, `#E4E4E7` border, `#09090B` active tab icon/label, and `#F4F4F5` background pill.
- **Action Cards & Metric Tiles**: Minimalist white background `#FFFFFF`, 1px `#E4E4E7` border, dark icon containers `#F4F4F5` with `#09090B` icons.
- **Form Inputs & Buttons**: `#FFFFFF` fill, `#E4E4E7` border, `#09090B` focus border, 10px corner radius.

---

## 🏛️ Architecture & Core Components

### 1. State Management & Navigation
- **Riverpod Providers**:
  - `authStateProvider`: Manages `AsyncValue<AppUser?>` authentication state and auto-logout on HTTP 401.
  - `attendanceProvider`: Manages `AsyncValue<AttendanceState>` for daily shift check-in/out and visit counters.
  - `syncProvider`: Tracks pending offline queue count and listens to connectivity streams.
  - `appConfigProvider`: Holds dynamic app configurations (`AppConfig`).
- **GoRouter Configuration**:
  - Defined in `lib/app.dart`.
  - `ShellRoute` wraps main tabs in `HomeScreen` with persistent bottom navigation.
  - Automatic redirect guards for `/login` vs `/home`.

### 2. Null-Safety & Safe Deserialization Rules
- **Boolean Parsing**:
  - Always deserialize API boolean values explicitly checking `== true || == 1` to prevent `Null` or integer `0` / `1` mismatch:
    ```dart
    isActive: json['is_active'] == true || json['is_active'] == 1 || json['is_active'] == null,
    canAccessRestrictedModules: json['can_access_restricted_modules'] == true || json['can_access_restricted_modules'] == 1,
    ```
- **AttendanceState Deserialization**:
  - In `AttendanceState.fromJson`, ensure missing or null `checked_in` keys default safely to `notCheckedIn()`:
    ```dart
    final checkedIn = json['checked_in'] == true || json['checked_in'] == 1;
    if (!checkedIn) return AttendanceState.notCheckedIn();
    ```
- **User Initials & Name Handling**:
  - Split string names safely using whitespace regex `RegExp(r'\s+')` and filter empty tokens to avoid `RangeError`:
    ```dart
    String get initials {
      final parts = fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
      if (parts.length >= 2) return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
      if (parts.isNotEmpty) return parts[0][0].toUpperCase();
      return '?';
    }
    ```

### 3. Native Platform Channel & Service Safety
- **Geolocator GPS Checks**:
  - Always convert platform channel location service check results to boolean:
    ```dart
    bool serviceEnabled = (await Geolocator.isLocationServiceEnabled()) == true;
    ```
- **Connectivity Checks**:
  - Wrap connectivity stream and status checks in `try/catch` to handle platform channel exceptions cleanly:
    ```dart
    Future<bool> _isOnline() async {
      try {
        final result = await Connectivity().checkConnectivity();
        return result.isNotEmpty && !result.contains(ConnectivityResult.none);
      } catch (_) {
        return false;
      }
    }
    ```

---

## 🔍 Common Issues & Resolved Troubleshooting

### 1. `type 'Null' is not a subtype of type 'bool' of 'function result'`
- **Symptom**: Red screen error widget displaying during `DashboardTab` or app startup.
- **Root Cause**:
  1. `AttendanceState.fromJson` checked `if (json['checked_in'] == false)` which evaluated to `false` when `checked_in` key was missing or `null`, inadvertently instantiating `AttendanceState(checkedIn: true, ...)` with a `null` `checkinTime`.
  2. Platform channel calls like `Geolocator.isLocationServiceEnabled()` returning `null` dynamically into non-nullable `bool` variables.
  3. `fullName` splitting without null/empty safeguards.
- **Resolution**: Applied strict boolean checks `== true || == 1`, null-safe string splitting, and wrapped platform channel awaits with explicit boolean coercions.

---

## 🧪 Testing Verification
Run mobile Flutter unit and widget tests:
```bash
cd mobile
flutter test
```
