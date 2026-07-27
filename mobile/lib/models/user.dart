class AppUser {
  final int id;
  final String username;
  final String fullName;
  final String email;
  final String role;
  final String? employeeId;
  final String? phone;
  final int? companyProfileId;
  final bool isActive;
  final bool canAccessRestrictedModules;

  AppUser({
    required this.id,
    required this.username,
    required this.fullName,
    required this.email,
    required this.role,
    this.employeeId,
    this.phone,
    this.companyProfileId,
    required this.isActive,
    this.canAccessRestrictedModules = false,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
    id: json['id'] ?? json['user_id'] ?? 0,
    username: json['username'] ?? '',
    fullName: json['full_name'] ?? '',
    email: json['email'] ?? '',
    role: json['role'] ?? '',
    employeeId: json['employee_id'],
    phone: json['phone'],
    companyProfileId: json['company_profile_id'],
    isActive: json['is_active'] == true || json['is_active'] == 1 || json['is_active'] == null,
    canAccessRestrictedModules: json['can_access_restricted_modules'] == true || json['can_access_restricted_modules'] == 1,
  );

  bool get isL2OrAbove =>
      role == 'territory_manager' ||
      role == 'admin' ||
      canAccessRestrictedModules;

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.length >= 2) return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    if (parts.isNotEmpty) return parts[0][0].toUpperCase();
    return '?';
  }
}

class AppConfig {
  final String paymentMode;
  final bool denominationMandatory;
  final int gpsThresholdMetres;
  final int syncIntervalSeconds;

  AppConfig({
    required this.paymentMode,
    required this.denominationMandatory,
    required this.gpsThresholdMetres,
    required this.syncIntervalSeconds,
  });

  factory AppConfig.fromJson(Map<String, dynamic> json) => AppConfig(
    paymentMode: json['payment_mode'] ?? 'cash_and_online',
    denominationMandatory: json['denomination_mandatory'] ?? false,
    gpsThresholdMetres: json['gps_threshold_metres'] ?? 100,
    syncIntervalSeconds: json['sync_interval_seconds'] ?? 300,
  );

  bool get allowCash =>
    paymentMode == 'cash_only' || paymentMode == 'cash_and_online';
  bool get allowOnline =>
    paymentMode == 'online_only' || paymentMode == 'cash_and_online';

  static AppConfig get defaults => AppConfig(
    paymentMode: 'cash_and_online',
    denominationMandatory: false,
    gpsThresholdMetres: 100,
    syncIntervalSeconds: 300,
  );
}
