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
      _showSnackBar('Please enter your registered email, username, or phone number', const Color(0xFFDC2626));
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
        _showSnackBar('OTP code sent successfully to ${res['email'] ?? loginInput}', const Color(0xFF16A34A));
      }
    } catch (e) {
      if (mounted) {
        String errorMsg = 'Failed to request OTP. Check your connection or username.';
        if (e is DioException) {
          final data = e.response?.data;
          if (data is Map && data.containsKey('detail')) {
            errorMsg = data['detail'].toString();
          } else if (e.type == DioExceptionType.connectionError || e.type == DioExceptionType.connectionTimeout) {
            errorMsg = 'Cannot connect to server at 127.0.0.1:8090. Ensure backend is running.';
          } else if (e.message != null && e.message!.isNotEmpty) {
            errorMsg = e.message!;
          }
        }
        _showSnackBar(errorMsg, const Color(0xFFDC2626));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _verifyOtp() async {
    final otpCode = _otpCtrl.text.trim();
    if (otpCode.isEmpty || otpCode.length < 6) {
      _showSnackBar('Please enter the 6-digit OTP code sent to your email', const Color(0xFFDC2626));
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
          } else if (e.type == DioExceptionType.connectionError || e.type == DioExceptionType.connectionTimeout) {
            errorMsg = 'Cannot connect to server at 127.0.0.1:8090. Ensure backend is running.';
          } else if (e.message != null && e.message!.isNotEmpty) {
            errorMsg = e.message!;
          }
        }
        _showSnackBar(errorMsg, const Color(0xFFDC2626));
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
      backgroundColor: const Color(0xFF09090B), // Zinc 950
      body: SingleChildScrollView(
        child: SizedBox(
          height: size.height,
          child: Stack(
            children: [
              // Top branding header section
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                height: size.height * 0.35,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  color: const Color(0xFF09090B),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF18181B),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFF27272A), width: 1),
                        ),
                        child: const Icon(
                          Icons.lock_outline_rounded,
                          color: Colors.white,
                          size: 28,
                        ),
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Safar Mobile',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.8,
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Passwordless Sales Operations Portal',
                        style: TextStyle(
                          color: Color(0xFFA1A1AA),
                          fontSize: 13,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Bottom card sheet
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                height: size.height * 0.68,
                child: Container(
                  padding: const EdgeInsets.fromLTRB(28, 32, 28, 24),
                  decoration: const BoxDecoration(
                    color: Color(0xFFFAFAFA), // Zinc 50
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(24),
                      topRight: Radius.circular(24),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _otpSent ? 'Enter Verification Code' : 'Sign In',
                        style: const TextStyle(
                          color: Color(0xFF09090B),
                          fontWeight: FontWeight.w800,
                          fontSize: 22,
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _otpSent
                            ? 'Enter the 6-digit OTP code sent to ${_sentTarget ?? 'your email'}.'
                            : 'Enter your registered email or username to receive a login code.',
                        style: const TextStyle(
                          color: Color(0xFF71717A),
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 28),

                      if (!_otpSent) ...[
                        TextField(
                          controller: _loginCtrl,
                          keyboardType: TextInputType.emailAddress,
                          style: const TextStyle(color: Color(0xFF09090B), fontSize: 14),
                          decoration: InputDecoration(
                            labelText: 'Email or Username / Mobile',
                            hintText: 'e.g. rep1@safar.com',
                            prefixIcon: const Icon(Icons.person_outline_rounded, size: 20, color: Color(0xFF71717A)),
                            filled: true,
                            fillColor: Colors.white,
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(color: Color(0xFFE4E4E7), width: 1.0),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(color: Color(0xFF09090B), width: 1.5),
                            ),
                          ),
                          onSubmitted: (_) => _requestOtp(),
                        ),
                        const Spacer(),
                        SizedBox(
                          width: double.infinity,
                          height: 48,
                          child: ElevatedButton(
                            onPressed: _loading ? null : _requestOtp,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF09090B),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                              elevation: 0,
                            ),
                            child: _loading
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Text(
                                    'Send Login OTP',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: -0.2,
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
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 8,
                            color: Color(0xFF09090B),
                          ),
                          decoration: InputDecoration(
                            labelText: '6-Digit OTP Code',
                            hintText: '123456',
                            counterText: '',
                            prefixIcon: const Icon(Icons.shield_outlined, size: 20, color: Color(0xFF71717A)),
                            filled: true,
                            fillColor: Colors.white,
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(color: Color(0xFFE4E4E7), width: 1.0),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(color: Color(0xFF09090B), width: 1.5),
                            ),
                          ),
                          onSubmitted: (_) => _verifyOtp(),
                        ),
                        const SizedBox(height: 12),
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
                              child: const Text('Change Email / Username', style: TextStyle(color: Color(0xFF71717A), fontSize: 12)),
                            ),
                            TextButton(
                              onPressed: _loading ? null : _requestOtp,
                              child: const Text('Resend OTP', style: TextStyle(color: Color(0xFF09090B), fontWeight: FontWeight.bold, fontSize: 12)),
                            ),
                          ],
                        ),
                        const Spacer(),
                        SizedBox(
                          width: double.infinity,
                          height: 48,
                          child: ElevatedButton(
                            onPressed: _loading ? null : _verifyOtp,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF09090B),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                              elevation: 0,
                            ),
                            child: _loading
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Text(
                                    'Verify & Sign In',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: -0.2,
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
