import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // ── Shadcn Light Tokens (Zinc / Neutral) ─────────────────────────
  static const Color lightBackground = Color(0xFFFAFAFA); // Zinc 50
  static const Color lightSurface = Color(0xFFFFFFFF);    // Pure White
  static const Color lightSurfaceAlt = Color(0xFFF4F4F5); // Zinc 100
  static const Color lightPrimary = Color(0xFF09090B);    // Zinc 950 (Black)
  static const Color lightPrimaryLight = Color(0xFF18181B);// Zinc 900
  static const Color lightSuccess = Color(0xFF10B981);
  static const Color lightWarning = Color(0xFFF59E0B);
  static const Color lightDanger = Color(0xFFDC2626);
  static const Color lightTextPrimary = Color(0xFF09090B); // Zinc 950
  static const Color lightTextSecondary = Color(0xFF71717A);// Zinc 500
  static const Color lightBorder = Color(0xFFE4E4E7);    // Zinc 200

  // ── Shadcn Dark Tokens ───────────────────────────────────────────
  static const Color darkBackground = Color(0xFF09090B);  // Zinc 950
  static const Color darkSurface = Color(0xFF18181B);     // Zinc 900
  static const Color darkSurfaceAlt = Color(0xFF27272A);  // Zinc 800
  static const Color darkPrimary = Color(0xFFFAFAFA);     // Zinc 50 (White)
  static const Color darkPrimaryLight = Color(0xFFE4E4E7); // Zinc 200
  static const Color darkSuccess = Color(0xFF10B981);
  static const Color darkWarning = Color(0xFFF59E0B);
  static const Color darkDanger = Color(0xFFEF4444);
  static const Color darkTextPrimary = Color(0xFFFAFAFA);  // Zinc 50
  static const Color darkTextSecondary = Color(0xFFA1A1AA);// Zinc 400
  static const Color darkBorder = Color(0xFF27272A);     // Zinc 800

  static ThemeData get light {
    return ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: lightBackground,
      colorScheme: const ColorScheme.light(
        primary: lightPrimary,
        secondary: lightPrimaryLight,
        surface: lightSurface,
        error: lightDanger,
        onPrimary: Colors.white,
        onSurface: lightTextPrimary,
      ),
      textTheme: GoogleFonts.interTextTheme(ThemeData.light().textTheme).copyWith(
        headlineLarge: GoogleFonts.inter(
          color: lightTextPrimary, fontSize: 26, fontWeight: FontWeight.w800, letterSpacing: -0.8),
        headlineMedium: GoogleFonts.inter(
          color: lightTextPrimary, fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5),
        titleLarge: GoogleFonts.inter(
          color: lightTextPrimary, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: -0.4),
        titleMedium: GoogleFonts.inter(
          color: lightTextPrimary, fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: -0.2),
        bodyLarge: GoogleFonts.inter(color: lightTextPrimary, fontSize: 14, fontWeight: FontWeight.w400),
        bodyMedium: GoogleFonts.inter(color: lightTextSecondary, fontSize: 13, fontWeight: FontWeight.w400),
        labelSmall: GoogleFonts.inter(
          color: lightTextSecondary, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: lightSurface,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.inter(
          color: lightTextPrimary, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: -0.4),
        iconTheme: const IconThemeData(color: lightTextPrimary),
        shape: const Border(
          bottom: BorderSide(color: lightBorder, width: 1.0),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: lightSurface,
        selectedItemColor: lightPrimary,
        unselectedItemColor: lightTextSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: lightPrimary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: -0.2),
          elevation: 0,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: lightSurfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: lightBorder, width: 1.0),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: lightBorder, width: 1.0),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: lightPrimary, width: 1.5),
        ),
        labelStyle: GoogleFonts.inter(color: lightTextSecondary, fontSize: 13),
        hintStyle: GoogleFonts.inter(color: lightTextSecondary, fontSize: 13),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
      cardTheme: CardThemeData(
        color: lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: lightBorder, width: 1.0),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      ),
      dividerTheme: const DividerThemeData(color: lightBorder, thickness: 1.0),
      useMaterial3: true,
    );
  }

  static ThemeData get dark {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkBackground,
      colorScheme: const ColorScheme.dark(
        primary: darkPrimary,
        secondary: darkPrimaryLight,
        surface: darkSurface,
        error: darkDanger,
        onPrimary: darkBackground,
        onSurface: darkTextPrimary,
      ),
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme).copyWith(
        headlineLarge: GoogleFonts.inter(
          color: darkTextPrimary, fontSize: 26, fontWeight: FontWeight.w800, letterSpacing: -0.8),
        headlineMedium: GoogleFonts.inter(
          color: darkTextPrimary, fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.5),
        titleLarge: GoogleFonts.inter(
          color: darkTextPrimary, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: -0.4),
        titleMedium: GoogleFonts.inter(
          color: darkTextPrimary, fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: -0.2),
        bodyLarge: GoogleFonts.inter(color: darkTextPrimary, fontSize: 14, fontWeight: FontWeight.w400),
        bodyMedium: GoogleFonts.inter(color: darkTextSecondary, fontSize: 13, fontWeight: FontWeight.w400),
        labelSmall: GoogleFonts.inter(
          color: darkTextSecondary, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: darkBackground,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.inter(
          color: darkTextPrimary, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: -0.4),
        iconTheme: const IconThemeData(color: darkTextPrimary),
        shape: const Border(
          bottom: BorderSide(color: darkBorder, width: 1.0),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: darkSurface,
        selectedItemColor: darkPrimary,
        unselectedItemColor: darkTextSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: darkPrimary,
          foregroundColor: darkBackground,
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: -0.2),
          elevation: 0,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkSurfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: darkBorder, width: 1.0),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: darkBorder, width: 1.0),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: darkPrimary, width: 1.5),
        ),
        labelStyle: GoogleFonts.inter(color: darkTextSecondary, fontSize: 13),
        hintStyle: GoogleFonts.inter(color: darkTextSecondary, fontSize: 13),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
      cardTheme: CardThemeData(
        color: darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: darkBorder, width: 1.0),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      ),
      dividerTheme: const DividerThemeData(color: darkBorder, thickness: 1.0),
      useMaterial3: true,
    );
  }
}
