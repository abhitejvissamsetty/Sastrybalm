import 'package:intl/intl.dart';

class DateFormatter {
  static DateTime parseDateTime(String isoString) {
    if (isoString.isEmpty) return DateTime.now();
    try {
      // Clean string
      final cleanStr = isoString.trim();
      // If it contains timezone designation, parse and convert to local
      if (cleanStr.endsWith('Z') || cleanStr.contains('+')) {
        return DateTime.parse(cleanStr).toLocal();
      }
      // Naive IST datetime string from server (e.g., 2026-07-27T19:18:00)
      return DateTime.parse(cleanStr);
    } catch (_) {
      return DateTime.now();
    }
  }

  static String formatTime(DateTime dt) {
    return DateFormat('hh:mm a').format(dt);
  }

  static String formatDate(DateTime dt) {
    return DateFormat('dd MMM yyyy').format(dt);
  }

  static String formatDateTime(DateTime dt) {
    return DateFormat('dd MMM yyyy, hh:mm a').format(dt);
  }
}
