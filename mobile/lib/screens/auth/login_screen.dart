import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';
import '../../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _loginCtrl = TextEditingController();
  final _otpCtrl = TextEditingController();
  bool _otpSent = false;
  bool _loading = false;
  String? _sentTarget;

  Future<void> _requestOtp() async {
    final loginInput = _loginCtrl.text.trim();
    if (loginInput.isEmpty) {
      _showSnackBar('Please enter your registered email, username, or phone number', Colors.red.shade700);
      return;
    }

    setState(() => _loading = true);
    try {
      final service = ref.read(authServiceProvider);
      final res = await service.requestOtp(loginInput);
      if (mounted) {
        setState(() {
          _otpSent = true;
          _sentTarget = res['email'] ?? loginInput;
        });
        _showSnackBar('OTP code sent successfully to ${res['email'] ?? loginInput}', Colors.green.shade700);
      }
    } catch (e) {
      if (mounted) {
        String errorMsg = 'Failed to request OTP. Check your connection or username.';
        if (e is DioException) {
          final data = e.response?.data;
          if (data is Map && data.containsKey('detail')) {
            errorMsg = data['detail'].toString();
          }
        }
        _showSnackBar(errorMsg, Colors.red.shade700);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _verifyOtp() async {
    final otpCode = _otpCtrl.text.trim();
    if (otpCode.isEmpty || otpCode.length < 6) {
      _showSnackBar('Please enter the 6-digit OTP code sent to your email', Colors.red.shade700);
      return;
    }

    setState(() => _loading = true);
    try {
      final loginInput = _loginCtrl.text.trim();
      await ref.read(authStateProvider.notifier).verifyOtp(loginInput, otpCode);
      if (mounted) context.go('/home');
    } catch (e) {
      if (mounted) {
        String errorMsg = 'Invalid or expired OTP code';
        if (e is DioException) {
          final data = e.response?.data;
          if (data is Map && data.containsKey('detail')) {
            errorMsg = data['detail'].toString();
          }
        }
        _showSnackBar(errorMsg, Colors.red.shade700);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showSnackBar(String message, Color bgColor) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: bgColor,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  void dispose() {
    _loginCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;

    return Scaffold(
      backgroundColor: theme.colorScheme.primary,
      body: SingleChildScrollView(
        child: SizedBox(
          height: size.height,
          child: Stack(
            children: [
              // Top branding section
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                height: size.height * 0.38,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 32),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primary,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(
                          Icons.mark_email_read_rounded,
                          color: Colors.white,
                          size: 36,
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'Sastrybalm SFA',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 32,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -1.0,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Secure Passwordless Email OTP Authentication',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.85),
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Bottom card
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                height: size.height * 0.65,
                child: Container(
                  padding: const EdgeInsets.fromLTRB(30, 36, 30, 24),
                  decoration: BoxDecoration(
                    color: theme.scaffoldBackgroundColor,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(36),
                      topRight: Radius.circular(36),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.15),
                        blurRadius: 25,
                        offset: const Offset(0, -5),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _otpSent ? 'Enter Verification Code' : 'Welcome Back',
                        style: theme.textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                          fontSize: 24,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _otpSent
                            ? 'Enter the 6-digit OTP code sent to ${_sentTarget ?? 'your email'}.'
                            : 'Enter your registered email or username to receive a login OTP.',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(height: 32),

                      if (!_otpSent) ...[
                        TextField(
                          controller: _loginCtrl,
                          keyboardType: TextInputType.emailAddress,
                          style: theme.textTheme.bodyLarge,
                          decoration: InputDecoration(
                            labelText: 'Email or Username / Mobile',
                            hintText: 'e.g. rajesh.rep@sastrybalm.com or rep1',
                            prefixIcon: const Icon(Icons.person_outline_rounded),
                            filled: true,
                            fillColor: theme.colorScheme.surface,
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(
                                color: theme.colorScheme.primary.withOpacity(0.12),
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(
                                color: theme.colorScheme.primary,
                                width: 1.5,
                              ),
                            ),
                          ),
                          onSubmitted: (_) => _requestOtp(),
                        ),
                        const Spacer(),
                        SizedBox(
                          width: double.infinity,
                          height: 54,
                          child: ElevatedButton(
                            onPressed: _loading ? null : _requestOtp,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: theme.colorScheme.primary,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(18),
                              ),
                              elevation: 4,
                            ),
                            child: _loading
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Text(
                                    'Send Login OTP',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                          ),
                        ),
                      ] else ...[
                        TextField(
                          controller: _otpCtrl,
                          keyboardType: TextInputType.number,
                          maxLength: 6,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 8,
                          ),
                          decoration: InputDecoration(
                            labelText: '6-Digit OTP Code',
                            hintText: '123456',
                            counterText: '',
                            prefixIcon: const Icon(Icons.shield_outlined),
                            filled: true,
                            fillColor: theme.colorScheme.surface,
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(
                                color: theme.colorScheme.primary.withOpacity(0.12),
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(
                                color: theme.colorScheme.primary,
                                width: 1.5,
                              ),
                            ),
                          ),
                          onSubmitted: (_) => _verifyOtp(),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            TextButton(
                              onPressed: () {
                                setState(() {
                                  _otpSent = false;
                                  _otpCtrl.clear();
                                });
                              },
                              child: const Text('Change Email / Username'),
                            ),
                            TextButton(
                              onPressed: _loading ? null : _requestOtp,
                              child: const Text('Resend OTP'),
                            ),
                          ],
                        ),
                        const Spacer(),
                        SizedBox(
                          width: double.infinity,
                          height: 54,
                          child: ElevatedButton(
                            onPressed: _loading ? null : _verifyOtp,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: theme.colorScheme.primary,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(18),
                              ),
                              elevation: 4,
                            ),
                            child: _loading
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Text(
                                    'Verify & Login',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
