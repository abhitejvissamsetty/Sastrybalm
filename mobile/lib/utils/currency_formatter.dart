import 'package:intl/intl.dart';

class CurrencyFormatter {
  static final _indianRupeeFormat = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 2,
  );

  static String format(double amount) {
    return _indianRupeeFormat.format(amount);
  }

  static String formatNoDecimal(double amount) {
    return NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 0,
    ).format(amount);
  }
}
