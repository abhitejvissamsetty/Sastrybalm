import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';

final apiClientProvider = Provider((ref) => ApiClient());

final authServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return AuthService(client);
});

final appConfigProvider = StateProvider<AppConfig?>((ref) => null);

final authStateProvider =
    StateNotifierProvider<AuthNotifier, AsyncValue<AppUser?>>((ref) {
  return AuthNotifier(ref.read(authServiceProvider), ref);
});

class AuthNotifier extends StateNotifier<AsyncValue<AppUser?>> {
  final AuthService _authService;
  final Ref _ref;
  StreamSubscription<bool>? _unauthorizedSub;

  AuthNotifier(this._authService, this._ref)
      : super(const AsyncValue.loading()) {
    _init();
    // Listen for 401 events from the API client and auto-logout
    _unauthorizedSub =
        ApiClient().onUnauthorized.listen((_) => _handleForceLogout());
  }

  Future<void> _init() async {
    final hasToken = await _authService.isLoggedIn();
    if (hasToken) {
      try {
        final user = await _authService.me();
        await loadConfig();
        state = AsyncValue.data(user);
      } catch (_) {
        state = const AsyncValue.data(null);
      }
    } else {
      state = const AsyncValue.data(null);
    }
  }

  /// Called automatically when the API returns HTTP 401.
  void _handleForceLogout() {
    _authService.logout();
    _ref.read(appConfigProvider.notifier).state = null;
    state = const AsyncValue.data(null);
  }

  Future<void> loadConfig() async {
    try {
      final config = await _authService.fetchConfig();
      _ref.read(appConfigProvider.notifier).state = config;
    } catch (_) {
      _ref.read(appConfigProvider.notifier).state = AppConfig.defaults;
    }
  }

  Future<void> login(String username, String password) async {
    state = const AsyncValue.loading();
    try {
      final user = await _authService.login(username, password);
      await loadConfig();
      state = AsyncValue.data(user);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    _ref.read(appConfigProvider.notifier).state = null;
    state = const AsyncValue.data(null);
  }

  @override
  void dispose() {
    _unauthorizedSub?.cancel();
    super.dispose();
  }
}
