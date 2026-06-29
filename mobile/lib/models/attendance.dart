import '../utils/date_formatter.dart';

class AttendanceState {
  final bool checkedIn;
  final int? timesheetId;
  final DateTime? checkinTime;
  final DateTime? checkoutTime;
  final int visitCount;
  final String status;

  AttendanceState({
    required this.checkedIn,
    this.timesheetId,
    this.checkinTime,
    this.checkoutTime,
    this.visitCount = 0,
    this.status = 'unknown',
  });

  factory AttendanceState.notCheckedIn() => AttendanceState(checkedIn: false);

  factory AttendanceState.fromJson(Map<String, dynamic> json) {
    if (json['checked_in'] == false) return AttendanceState.notCheckedIn();
    return AttendanceState(
      checkedIn: true,
      timesheetId: json['id'],
      checkinTime: json['checkin_time'] != null
          ? DateFormatter.parseDateTime(json['checkin_time']) : null,
      checkoutTime: json['checkout_time'] != null
          ? DateFormatter.parseDateTime(json['checkout_time']) : null,
      visitCount: json['visit_count'] ?? 0,
      status: json['status'] ?? 'open',
    );
  }

  bool get isOpen => status == 'open';
  bool get isClosed => status == 'closed';
  Duration? get workedDuration {
    if (checkinTime == null) return null;
    final end = checkoutTime ?? DateTime.now();
    return end.difference(checkinTime!);
  }
}

class VisitRecord {
  final int id;
  final int outletId;
  final double? distanceFromOutlet;
  final DateTime visitTime;
  final DateTime? checkoutTime;
  final bool flagged;

  VisitRecord({
    required this.id,
    required this.outletId,
    this.distanceFromOutlet,
    required this.visitTime,
    this.checkoutTime,
    this.flagged = false,
  });

  factory VisitRecord.fromJson(Map<String, dynamic> json) => VisitRecord(
    id: json['id'],
    outletId: json['outlet_id'] ?? 0,
    distanceFromOutlet: (json['distance_from_outlet'] as num?)?.toDouble(),
    visitTime: DateFormatter.parseDateTime(json['visit_time']),
    checkoutTime: json['checkout_time'] != null
        ? DateFormatter.parseDateTime(json['checkout_time']) : null,
    flagged: json['flagged'] ?? false,
  );

  bool get isActive => checkoutTime == null;
  Duration get duration =>
    (checkoutTime ?? DateTime.now()).difference(visitTime);
}

class Payment {
  final int id;
  final String paymentRef;
  final String status;
  final double amount;
  final String method;
  final int outletId;

  Payment({
    required this.id,
    required this.paymentRef,
    required this.status,
    required this.amount,
    required this.method,
    required this.outletId,
  });

  factory Payment.fromJson(Map<String, dynamic> json) => Payment(
    id: json['id'],
    paymentRef: json['payment_ref'],
    status: json['status'],
    amount: (json['amount'] as num).toDouble(),
    method: json['method'],
    outletId: json['outlet_id'],
  );
}
