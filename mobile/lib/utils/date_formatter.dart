import 'package:intl/intl.dart';

class DateFormatter {
  static DateTime parseDateTime(String isoString) {
    if (isoString.isEmpty) return DateTime.now();
    // If no timezone offset or Z suffix is present, assume UTC and parse accordingly.
    if (!isoString.endsWith('Z') &&
        !isoString.contains('+') &&
        !isoString.contains(RegExp(r'-\d\d:\d\d$'))) {
      return DateTime.parse('${isoString}Z').toLocal();
    }
    return DateTime.parse(isoString).toLocal();
  }

  static String formatTime(DateTime dt) {
    return DateFormat('hh:mm a').format(dt.toLocal());
  }

  static String formatDate(DateTime dt) {
    return DateFormat('dd MMM yyyy').format(dt.toLocal());
  }

  static String formatDateTime(DateTime dt) {
    return DateFormat('dd MMM yyyy, hh:mm a').format(dt.toLocal());
  }
}
