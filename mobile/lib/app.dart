import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'config/app_theme.dart';
import 'providers/auth_provider.dart';
import 'screens/auth/login_screen.dart';
import 'models/user.dart';
import 'screens/home/home_screen.dart';
import 'screens/home/dashboard_tab.dart';
import 'screens/beat/beat_plan_screen.dart';
import 'screens/beat/outlet_detail_screen.dart';
import 'screens/visit/visit_screen.dart';
import 'screens/orders/order_create_screen.dart';
import 'screens/orders/order_list_screen.dart';
import 'screens/orders/order_detail_screen.dart';
import 'screens/payments/payment_collect_screen.dart';
import 'screens/payments/payment_submit_screen.dart';
import 'screens/expenses/expense_screen.dart';
import 'screens/material_requests/mr_screen.dart';
import 'screens/asset_capitalization/asset_cap_screen.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final listenable = ValueNotifier<AsyncValue<AppUser?>>(const AsyncValue.loading());
  
  // Listen to the authStateProvider to update GoRouter's refreshListenable
  ref.listen<AsyncValue<AppUser?>>(authStateProvider, (previous, next) {
    listenable.value = next;
  });

  // Also initialize the listenable with the current value
  final initialValue = ref.read(authStateProvider);
  listenable.value = initialValue;

  return GoRouter(
    navigatorKey: navigatorKey,
    initialLocation: '/home',
    refreshListenable: listenable,
    redirect: (context, state) {
      final authState = listenable.value;
      final isLoggedIn = authState.valueOrNull != null;
      final isLoginPage = state.matchedLocation == '/login';

      // If still loading the initial auth state, don't redirect yet
      if (authState is AsyncLoading) return null;

      if (!isLoggedIn && !isLoginPage) return '/login';
      if (isLoggedIn && isLoginPage) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (ctx, _) => const LoginScreen()),
      ShellRoute(
        builder: (ctx, state, child) => HomeScreen(child: child),
        routes: [
          GoRoute(path: '/home', builder: (ctx, _) => const DashboardTab()),
          GoRoute(path: '/beat', builder: (ctx, _) => const BeatPlanScreen()),
          GoRoute(path: '/history', builder: (ctx, _) => const OrderListScreen()),
          GoRoute(path: '/order/new', builder: (ctx, _) => const OrderCreateScreen()),
          GoRoute(
            path: '/order/:id',
            builder: (ctx, state) => OrderDetailScreen(
              orderId: int.parse(state.pathParameters['id']!),
            ),
          ),
          GoRoute(
            path: '/outlet/:id',
            builder: (ctx, state) => OutletDetailScreen(
              outletId: int.parse(state.pathParameters['id']!),
            ),
          ),
          GoRoute(path: '/payment/collect', builder: (ctx, _) => const PaymentCollectScreen()),
          GoRoute(path: '/payment/submit', builder: (ctx, _) => const PaymentSubmitScreen()),
          GoRoute(path: '/expense', builder: (ctx, _) => const ExpenseScreen()),
          GoRoute(path: '/material-request', builder: (ctx, _) => const MrScreen()),
          GoRoute(path: '/asset-cap', builder: (ctx, _) => const AssetCapitalizationScreen()),
          GoRoute(path: '/visit', builder: (ctx, _) => const VisitScreen()),
        ],
      ),
    ],
  );
});

class MyApp extends ConsumerWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Sastrybalm SFA',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}
