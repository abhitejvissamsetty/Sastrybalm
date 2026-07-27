import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/sync_provider.dart';
import '../../widgets/gps_status_chip.dart';
import '../../utils/date_formatter.dart';

class DashboardTab extends ConsumerWidget {
  const DashboardTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(authStateProvider);
    final attendanceAsync = ref.watch(attendanceProvider);
    final syncCount = ref.watch(syncProvider);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFF6F8FC),
      body: SafeArea(
        child: RefreshIndicator(
          color: const Color(0xFF4F46E5),
          onRefresh: () async {
            ref.read(attendanceProvider.notifier).refresh();
            ref.read(syncProvider.notifier).updatePendingCount();
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Executive Top Header Bar ─────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        userAsync.when(
                          data: (user) => Container(
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFF6366F1).withOpacity(0.3),
                                  blurRadius: 10,
                                  offset: const Offset(0, 4),
                                ),
                              ],
                            ),
                            padding: const EdgeInsets.all(2),
                            child: CircleAvatar(
                              backgroundColor: Colors.white,
                              radius: 23,
                              child: Text(
                                user?.initials ?? 'SR',
                                style: const TextStyle(
                                  color: Color(0xFF4F46E5),
                                  fontWeight: FontWeight.w900,
                                  fontSize: 15,
                                ),
                              ),
                            ),
                          ),
                          loading: () => const CircleAvatar(
                            radius: 23,
                            child: SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          ),
                          error: (_, __) => const CircleAvatar(
                            radius: 23,
                            child: Icon(Icons.person),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            userAsync.when(
                              data: (user) => Text(
                                'Hi, ${user?.fullName.split(' ')[0] ?? 'Sales Rep'}',
                                style: const TextStyle(
                                  color: Color(0xFF0F172A),
                                  fontWeight: FontWeight.w900,
                                  fontSize: 20,
                                  letterSpacing: -0.6,
                                ),
                              ),
                              loading: () => const Text('Loading...'),
                              error: (_, __) => const Text('Sales Rep'),
                            ),
                            const SizedBox(height: 2),
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFEEF2FF),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Row(
                                    children: [
                                      const Icon(Icons.calendar_today_rounded, size: 11, color: Color(0xFF4F46E5)),
                                      const SizedBox(width: 4),
                                      Text(
                                        DateFormatter.formatDate(DateTime.now()),
                                        style: const TextStyle(
                                          color: Color(0xFF4338CA),
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ],
                    ),
                    Row(
                      children: [
                        _buildHeaderIconButton(
                          icon: Icons.sync_rounded,
                          tooltip: 'Sync Data',
                          onTap: () {
                            ref.read(syncProvider.notifier).triggerSync();
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Syncing data with server...'),
                                behavior: SnackBarBehavior.floating,
                              ),
                            );
                          },
                        ),
                        const SizedBox(width: 8),
                        _buildHeaderIconButton(
                          icon: Icons.logout_rounded,
                          tooltip: 'Logout',
                          color: const Color(0xFFEF4444),
                          onTap: () {
                            showDialog(
                              context: context,
                              builder: (ctx) => AlertDialog(
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                title: const Text('Confirm Logout', style: TextStyle(fontWeight: FontWeight.bold)),
                                content: const Text('Are you sure you want to log out of your session?'),
                                actions: [
                                  TextButton(
                                    child: const Text('Cancel'),
                                    onPressed: () => Navigator.pop(ctx),
                                  ),
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFFEF4444),
                                      minimumSize: const Size(90, 40),
                                    ),
                                    child: const Text('Logout'),
                                    onPressed: () {
                                      Navigator.pop(ctx);
                                      ref.read(authStateProvider.notifier).logout();
                                    },
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // ── Vibrant Workday Hero Banner Card ───────────────────────────
                attendanceAsync.when(
                  data: (att) {
                    final isCheckedIn = att.checkedIn && att.isOpen;
                    return Container(
                      width: double.infinity,
                      clipBehavior: Clip.antiAlias,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: isCheckedIn
                              ? [const Color(0xFF059669), const Color(0xFF10B981), const Color(0xFF34D399)]
                              : [const Color(0xFF3B82F6), const Color(0xFF4F46E5), const Color(0xFF7C3AED)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(28),
                        boxShadow: [
                          BoxShadow(
                            color: (isCheckedIn ? const Color(0xFF10B981) : const Color(0xFF4F46E5)).withOpacity(0.35),
                            blurRadius: 24,
                            offset: const Offset(0, 10),
                          ),
                        ],
                      ),
                      child: Stack(
                        children: [
                          // Decorative 3D background ambient circles
                          Positioned(
                            right: -30,
                            top: -30,
                            child: Container(
                              width: 150,
                              height: 150,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: Colors.white.withOpacity(0.12),
                              ),
                            ),
                          ),
                          Positioned(
                            left: -40,
                            bottom: -40,
                            child: Container(
                              width: 120,
                              height: 120,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: Colors.black.withOpacity(0.08),
                              ),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                      decoration: BoxDecoration(
                                        color: Colors.white.withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(30),
                                        border: Border.all(color: Colors.white.withOpacity(0.3), width: 1),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Container(
                                            width: 8,
                                            height: 8,
                                            decoration: const BoxDecoration(
                                              color: Colors.white,
                                              shape: BoxShape.circle,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            isCheckedIn ? 'WORKDAY ACTIVE' : 'WORKDAY INACTIVE',
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 11,
                                              fontWeight: FontWeight.w900,
                                              letterSpacing: 0.8,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    const GpsStatusChip(),
                                  ],
                                ),
                                const SizedBox(height: 24),
                                Text(
                                  isCheckedIn ? 'Shift Active' : 'Ready to Start?',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 26,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: -0.5,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  isCheckedIn
                                      ? 'Your shift check-in is confirmed. Beat route tracking & order booking are active.'
                                      : 'Check-in to enable orders, beats, payments, and customer check-ins.',
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(0.9),
                                    fontSize: 13,
                                    height: 1.45,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(height: 24),
                                Row(
                                  children: [
                                    Expanded(
                                      child: Container(
                                        decoration: BoxDecoration(
                                          borderRadius: BorderRadius.circular(16),
                                          boxShadow: [
                                            BoxShadow(
                                              color: Colors.black.withOpacity(0.12),
                                              blurRadius: 12,
                                              offset: const Offset(0, 4),
                                            ),
                                          ],
                                        ),
                                        child: ElevatedButton.icon(
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: Colors.white,
                                            foregroundColor: isCheckedIn ? const Color(0xFF059669) : const Color(0xFF4F46E5),
                                            shape: RoundedRectangleBorder(
                                              borderRadius: BorderRadius.circular(16),
                                            ),
                                            elevation: 0,
                                            padding: const EdgeInsets.symmetric(vertical: 14),
                                            minimumSize: const Size(double.infinity, 50),
                                          ),
                                          icon: Icon(
                                            isCheckedIn ? Icons.stop_circle_rounded : Icons.play_circle_fill_rounded,
                                            size: 20,
                                          ),
                                          label: Text(
                                            isCheckedIn ? 'Check Out of Shift' : 'Begin Workday',
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w900,
                                              fontSize: 15,
                                              letterSpacing: 0.3,
                                            ),
                                          ),
                                          onPressed: () async {
                                            try {
                                              if (isCheckedIn) {
                                                final notesCtrl = TextEditingController();
                                                final confirm = await showDialog<bool>(
                                                  context: context,
                                                  builder: (ctx) => AlertDialog(
                                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                                    title: const Text('End Workday', style: TextStyle(fontWeight: FontWeight.bold)),
                                                    content: Column(
                                                      mainAxisSize: MainAxisSize.min,
                                                      children: [
                                                        const Text('Are you sure you want to Check Out?'),
                                                        const SizedBox(height: 12),
                                                        TextField(
                                                          controller: notesCtrl,
                                                          decoration: const InputDecoration(
                                                            labelText: 'End of day notes',
                                                            hintText: 'e.g. Completed beat route',
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                    actions: [
                                                      TextButton(
                                                        child: const Text('Cancel'),
                                                        onPressed: () => Navigator.pop(ctx, false),
                                                      ),
                                                      ElevatedButton(
                                                        style: ElevatedButton.styleFrom(
                                                          backgroundColor: const Color(0xFFEF4444),
                                                          minimumSize: const Size(100, 40),
                                                        ),
                                                        child: const Text('Check Out'),
                                                        onPressed: () => Navigator.pop(ctx, true),
                                                      ),
                                                    ],
                                                  ),
                                                );

                                                if (confirm == true) {
                                                  await ref.read(attendanceProvider.notifier).checkOut(notes: notesCtrl.text.trim());
                                                }
                                              } else {
                                                await ref.read(attendanceProvider.notifier).checkIn();
                                              }
                                            } catch (e) {
                                              ScaffoldMessenger.of(context).showSnackBar(
                                                SnackBar(
                                                  content: Text('Error: ${e.toString().replaceAll('Exception:', '')}'),
                                                  backgroundColor: const Color(0xFFEF4444),
                                                  behavior: SnackBarBehavior.floating,
                                                ),
                                              );
                                            }
                                          },
                                        ),
                                      ),
                                    ),
                                    if (isCheckedIn && att.checkinTime != null) ...[
                                      const SizedBox(width: 12),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                        decoration: BoxDecoration(
                                          color: Colors.white.withOpacity(0.18),
                                          borderRadius: BorderRadius.circular(16),
                                          border: Border.all(color: Colors.white.withOpacity(0.25)),
                                        ),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            const Text(
                                              'START TIME',
                                              style: TextStyle(
                                                color: Colors.white70,
                                                fontSize: 9,
                                                fontWeight: FontWeight.w900,
                                                letterSpacing: 0.5,
                                              ),
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              DateFormatter.formatTime(att.checkinTime!),
                                              style: const TextStyle(
                                                color: Colors.white,
                                                fontSize: 14,
                                                fontWeight: FontWeight.w900,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                  loading: () => Container(
                    height: 160,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(28),
                    ),
                    child: const Center(child: CircularProgressIndicator()),
                  ),
                  error: (e, __) => Card(
                    child: ListTile(
                      title: const Text('Error loading attendance'),
                      subtitle: Text(e.toString()),
                      trailing: IconButton(
                        icon: const Icon(Icons.refresh),
                        onPressed: () => ref.read(attendanceProvider.notifier).refresh(),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 28),

                // ── Overview Metrics Section ──────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Overview Metrics',
                      style: TextStyle(
                        color: Color(0xFF0F172A),
                        fontWeight: FontWeight.w900,
                        fontSize: 17,
                        letterSpacing: -0.4,
                      ),
                    ),
                    TextButton.icon(
                      onPressed: () => context.go('/beat'),
                      icon: const Icon(Icons.route_rounded, size: 16, color: Color(0xFF4F46E5)),
                      label: const Text(
                        'View Route',
                        style: TextStyle(
                          color: Color(0xFF4F46E5),
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                attendanceAsync.when(
                  data: (att) {
                    final visits = att.checkedIn ? att.visitCount : 0;
                    return Row(
                      children: [
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            value: '$visits',
                            label: 'Customer Visits',
                            subtitle: 'Beat progress today',
                            icon: Icons.storefront_rounded,
                            accentColor: const Color(0xFF6366F1),
                            bgColor: const Color(0xFFEEF2FF),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            value: syncCount == 0 ? 'Synced' : '$syncCount Pending',
                            label: 'Sync Status',
                            subtitle: syncCount == 0 ? 'All data up to date' : 'Requires network',
                            icon: syncCount == 0 ? Icons.cloud_done_rounded : Icons.cloud_upload_rounded,
                            accentColor: syncCount == 0 ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
                            bgColor: syncCount == 0 ? const Color(0xFFECFDF5) : const Color(0xFFFFFBEB),
                          ),
                        ),
                      ],
                    );
                  },
                  loading: () => const SizedBox(),
                  error: (_, __) => const SizedBox(),
                ),
                const SizedBox(height: 28),

                // ── Quick Operational Actions Grid ────────────────────────────
                const Text(
                  'Quick Actions',
                  style: TextStyle(
                    color: Color(0xFF0F172A),
                    fontWeight: FontWeight.w900,
                    fontSize: 17,
                    letterSpacing: -0.4,
                  ),
                ),
                const SizedBox(height: 14),
                userAsync.when(
                  data: (user) {
                    final canAccessRestricted = user?.canAccessRestrictedModules ?? false;
                    return GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisSpacing: 14,
                      mainAxisSpacing: 14,
                      childAspectRatio: 1.3,
                      children: [
                        _buildActionTile(
                          context,
                          title: 'Record Payment',
                          subtitle: 'Cash & UPI entries',
                          icon: Icons.payments_rounded,
                          color: const Color(0xFFF59E0B),
                          bgColor: const Color(0xFFFFFBEB),
                          onTap: () => context.push('/payment/collect'),
                        ),
                        if (canAccessRestricted)
                          _buildActionTile(
                            context,
                            title: 'Log Expense',
                            subtitle: 'Claims & travel bills',
                            icon: Icons.receipt_long_rounded,
                            color: const Color(0xFF6366F1),
                            bgColor: const Color(0xFFEEF2FF),
                            onTap: () => context.push('/expense'),
                          )
                        else
                          _buildActionTile(
                            context,
                            title: 'Create Order',
                            subtitle: 'Book customer order',
                            icon: Icons.add_shopping_cart_rounded,
                            color: const Color(0xFF6366F1),
                            bgColor: const Color(0xFFEEF2FF),
                            onTap: () => context.push('/order/new'),
                          ),
                        if (canAccessRestricted)
                          _buildActionTile(
                            context,
                            title: 'Material Request',
                            subtitle: 'Stock & POSM allocation',
                            icon: Icons.inventory_2_rounded,
                            color: const Color(0xFF10B981),
                            bgColor: const Color(0xFFECFDF5),
                            onTap: () => context.push('/material-request'),
                          )
                        else
                          _buildActionTile(
                            context,
                            title: 'Beat Plan',
                            subtitle: 'Today\'s route outlets',
                            icon: Icons.map_rounded,
                            color: const Color(0xFF10B981),
                            bgColor: const Color(0xFFECFDF5),
                            onTap: () => context.go('/beat'),
                          ),
                        _buildActionTile(
                          context,
                          title: 'Asset Deploy',
                          subtitle: 'Equipment & coolers',
                          icon: Icons.build_circle_rounded,
                          color: const Color(0xFF06B6D4),
                          bgColor: const Color(0xFFCFFAFE),
                          onTap: () => context.push('/asset-cap'),
                        ),
                      ],
                    );
                  },
                  loading: () => const SizedBox(),
                  error: (_, __) => const SizedBox(),
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderIconButton({
    required IconData icon,
    required String tooltip,
    required VoidCallback onTap,
    Color color = const Color(0xFF475569),
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: IconButton(
        icon: Icon(icon, color: color, size: 20),
        tooltip: tooltip,
        onPressed: onTap,
      ),
    );
  }

  Widget _buildMetricTile(
    BuildContext context, {
    required String value,
    required String label,
    required String subtitle,
    required IconData icon,
    required Color accentColor,
    required Color bgColor,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(color: const Color(0xFFE2E8F0), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: accentColor, size: 22),
              ),
              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: accentColor,
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w900,
              color: const Color(0xFF0F172A),
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: Color(0xFF334155),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: Color(0xFF94A3B8),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionTile(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required Color bgColor,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: const Color(0xFFE2E8F0), width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.02),
                blurRadius: 10,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const SizedBox(height: 12),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF0F172A),
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF64748B),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
