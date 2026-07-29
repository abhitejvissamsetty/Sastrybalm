import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailCtrl = TextEditingController();
  final _otpCtrl = TextEditingController();
  bool _otpSent = false;
  bool _loading = false;

  Future<void> _requestOtp() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      _showSnackBar('Please enter a valid registered email address.');
      return;
    }

    setState(() => _loading = true);
    try {
      await ref.read(authStateProvider.notifier).requestOtp(email);
      if (mounted) {
        setState(() {
          _otpSent = true;
          _loading = false;
        });
        _showSuccessSnackBar('OTP verification code sent to your email.');
      }
    } catch (error) {
      if (!mounted) return;
      var message = 'Failed to send OTP code.';
      if (error is DioException) {
        final data = error.response?.data;
        if (data is Map && data['detail'] != null) {
          message = data['detail'].toString();
        } else if (error.type == DioExceptionType.connectionError ||
            error.type == DioExceptionType.connectionTimeout) {
          message = 'Cannot connect to the Safar server.';
        }
      }
      _showSnackBar(message);
      setState(() => _loading = false);
    }
  }

  Future<void> _verifyOtp() async {
    final email = _emailCtrl.text.trim();
    final otpCode = _otpCtrl.text.trim();
    if (otpCode.isEmpty || otpCode.length < 4) {
      _showSnackBar('Please enter the 6-digit OTP code.');
      return;
    }

    setState(() => _loading = true);
    try {
      await ref.read(authStateProvider.notifier).verifyOtp(email, otpCode);
      if (mounted) context.go('/home');
    } catch (error) {
      if (!mounted) return;
      var message = 'Invalid or expired OTP code.';
      if (error is DioException) {
        final data = error.response?.data;
        if (data is Map && data['detail'] != null) {
          message = data['detail'].toString();
        } else if (error.type == DioExceptionType.connectionError ||
            error.type == DioExceptionType.connectionTimeout) {
          message = 'Cannot connect to the Safar server.';
        }
      }
      _showSnackBar(message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: const Color(0xFFDC2626),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showSuccessSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: const Color(0xFF16A34A),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const silverOutline = Color(0xFF94A3B8); // Metallic silver border
    const silverFocusOutline = Color(0xFFE2E8F0); // Bright silver border
    const silverText = Color(0xFFCBD5E1);

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) SystemNavigator.pop();
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF000000), // Pure black background
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Header Branding Logo
                    Center(
                      child: Image.asset(
                        'assets/images/app_logo.png',
                        width: 170,
                        height: 170,
                        fit: BoxFit.contain,
                      ),
                    ),
                    const SizedBox(height: 12),

                    // App Subtitle / Status
                    Text(
                      _otpSent
                          ? 'Enter the 6-digit code sent to\n${_emailCtrl.text}'
                          : 'Sign in using Email OTP verification',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 15,
                        color: Color(0xFF94A3B8),
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 32),

                    if (!_otpSent) ...[
                      // Email Input Field with Silver Outline
                      TextField(
                        controller: _emailCtrl,
                        cursorColor: Colors.white,
                        cursorWidth: 2.0,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.done,
                        style: const TextStyle(color: Colors.white, fontSize: 16),
                        autofillHints: const [AutofillHints.email],
                        onSubmitted: (_) => _requestOtp(),
                        decoration: InputDecoration(
                          labelText: 'Registered Email Address',
                          labelStyle: const TextStyle(color: silverText, fontSize: 14),
                          hintText: 'name@company.com',
                          hintStyle: const TextStyle(color: Color(0xFF64748B)),
                          prefixIcon: const Icon(Icons.email_outlined, color: silverText),
                          filled: true,
                          fillColor: const Color(0xFF111827),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                            borderSide: const BorderSide(color: silverOutline, width: 1.5),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                            borderSide: const BorderSide(color: silverFocusOutline, width: 2),
                          ),
                        ),
                      ),
                      const SizedBox(height: 28),

                      // Primary Button (Metallic Silver / Crisp White CTA)
                      SizedBox(
                        height: 54,
                        child: ElevatedButton(
                          onPressed: _loading ? null : _requestOtp,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFE2E8F0),
                            foregroundColor: const Color(0xFF09090B),
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: const BorderSide(color: Colors.white, width: 1),
                            ),
                          ),
                          child: _loading
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Color(0xFF09090B),
                                  ),
                                )
                              : const Text(
                                  'Send OTP Code',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.3,
                                  ),
                                ),
                        ),
                      ),
                    ] else ...[
                      // OTP Code Field with Silver Outline
                      TextField(
                        controller: _otpCtrl,
                        cursorColor: Colors.white,
                        cursorWidth: 2.0,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                          letterSpacing: 10,
                        ),
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _verifyOtp(),
                        decoration: InputDecoration(
                          labelText: '6-Digit OTP Code',
                          labelStyle: const TextStyle(color: silverText, fontSize: 14),
                          prefixIcon: const Icon(Icons.pin_outlined, color: silverText),
                          counterText: '',
                          filled: true,
                          fillColor: const Color(0xFF111827),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                            borderSide: const BorderSide(color: silverOutline, width: 1.5),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                            borderSide: const BorderSide(color: silverFocusOutline, width: 2),
                          ),
                        ),
                      ),
                      const SizedBox(height: 28),

                      // Verify Button
                      SizedBox(
                        height: 54,
                        child: ElevatedButton(
                          onPressed: _loading ? null : _verifyOtp,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFE2E8F0),
                            foregroundColor: const Color(0xFF09090B),
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: const BorderSide(color: Colors.white, width: 1),
                            ),
                          ),
                          child: _loading
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Color(0xFF09090B),
                                  ),
                                )
                              : const Text(
                                  'Verify & Sign In',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.3,
                                  ),
                                ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          TextButton(
                            onPressed: _loading
                                ? null
                                : () {
                                    setState(() {
                                      _otpSent = false;
                                      _otpCtrl.clear();
                                    });
                                  },
                            child: const Text(
                              'Change Email',
                              style: TextStyle(color: silverText, fontSize: 14),
                            ),
                          ),
                          TextButton(
                            onPressed: _loading ? null : _requestOtp,
                            child: const Text(
                              'Resend OTP',
                              style: TextStyle(color: silverFocusOutline, fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
