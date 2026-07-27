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

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA), // Zinc 50
      body: SafeArea(
        child: RefreshIndicator(
          color: const Color(0xFF09090B),
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
                // ── Executive Minimal Header Bar ──────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        userAsync.when(
                          data: (user) => CircleAvatar(
                            backgroundColor: const Color(0xFF09090B), // Zinc 950
                            radius: 22,
                            child: Text(
                              user?.initials ?? 'SR',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                fontSize: 14,
                              ),
                            ),
                          ),
                          loading: () => const CircleAvatar(
                            radius: 22,
                            backgroundColor: Color(0xFFE4E4E7),
                            child: SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF09090B)),
                            ),
                          ),
                          error: (_, __) => const CircleAvatar(
                            radius: 22,
                            backgroundColor: Color(0xFF09090B),
                            child: Icon(Icons.person_rounded, color: Colors.white, size: 20),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            userAsync.when(
                              data: (user) {
                                final firstName = user != null && user.fullName.trim().isNotEmpty
                                    ? user.fullName.trim().split(RegExp(r'\s+'))[0]
                                    : 'Sales Rep';
                                return Text(
                                  'Hi, $firstName',
                                  style: const TextStyle(
                                    color: Color(0xFF09090B), // Zinc 950
                                    fontWeight: FontWeight.w800,
                                    fontSize: 19,
                                    letterSpacing: -0.5,
                                  ),
                                );
                              },
                              loading: () => const Text('Loading...', style: TextStyle(color: Color(0xFF71717A))),
                              error: (_, __) => const Text('Sales Rep', style: TextStyle(color: Color(0xFF09090B))),
                            ),
                            const SizedBox(height: 2),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF4F4F5), // Zinc 100
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: const Color(0xFFE4E4E7), width: 1),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.calendar_today_rounded, size: 10, color: Color(0xFF71717A)),
                                  const SizedBox(width: 5),
                                  Text(
                                    DateFormatter.formatDate(DateTime.now()),
                                    style: const TextStyle(
                                      color: Color(0xFF71717A),
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
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
                          color: const Color(0xFFDC2626), // Red 600
                          onTap: () {
                            showDialog(
                              context: context,
                              builder: (ctx) => AlertDialog(
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                                title: const Text('Confirm Logout', style: TextStyle(fontWeight: FontWeight.bold)),
                                content: const Text('Are you sure you want to log out of your session?'),
                                actions: [
                                  TextButton(
                                    child: const Text('Cancel', style: TextStyle(color: Color(0xFF71717A))),
                                    onPressed: () => Navigator.pop(ctx),
                                  ),
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFF09090B),
                                      foregroundColor: Colors.white,
                                      minimumSize: const Size(90, 38),
                                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
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

                // ── Sleek Workday Hero Card (shadcn Dark Zinc) ────────────────
                attendanceAsync.when(
                  data: (att) {
                    final isCheckedIn = att.checkedIn && att.isOpen;
                    return Container(
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: const Color(0xFF09090B), // Zinc 950
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: const Color(0xFF27272A), width: 1), // Zinc 800
                        boxShadow: const [
                          BoxShadow(
                            color: Color(0x1F000000),
                            blurRadius: 16,
                            offset: Offset(0, 6),
                          ),
                        ],
                      ),
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF18181B), // Zinc 900
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(color: const Color(0xFF27272A), width: 1),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Container(
                                      width: 6,
                                      height: 6,
                                      decoration: BoxDecoration(
                                        color: isCheckedIn ? const Color(0xFF22C55E) : const Color(0xFFA1A1AA),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      isCheckedIn ? 'WORKDAY ACTIVE' : 'WORKDAY INACTIVE',
                                      style: const TextStyle(
                                        color: Color(0xFFFAFAFA),
                                        fontSize: 10.5,
                                        fontWeight: FontWeight.w700,
                                        letterSpacing: 0.6,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const GpsStatusChip(),
                            ],
                          ),
                          const SizedBox(height: 20),
                          Text(
                            isCheckedIn ? 'Shift Active' : 'Ready to Start?',
                            style: const TextStyle(
                              color: Color(0xFFFAFAFA),
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -0.5,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            isCheckedIn
                                ? 'Your shift check-in is confirmed. Beat route tracking & order booking are active.'
                                : 'Check-in to enable orders, beats, payments, and customer check-ins.',
                            style: const TextStyle(
                              color: Color(0xFFA1A1AA), // Zinc 400
                              fontSize: 13,
                              height: 1.4,
                              fontWeight: FontWeight.w400,
                            ),
                          ),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton.icon(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.white,
                                    foregroundColor: const Color(0xFF09090B),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    elevation: 0,
                                    padding: const EdgeInsets.symmetric(vertical: 12),
                                    minimumSize: const Size(double.infinity, 46),
                                  ),
                                  icon: Icon(
                                    isCheckedIn ? Icons.stop_circle_outlined : Icons.play_circle_fill_rounded,
                                    size: 18,
                                    color: const Color(0xFF09090B),
                                  ),
                                  label: Text(
                                    isCheckedIn ? 'Check Out of Shift' : 'Begin Workday',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 14,
                                      letterSpacing: -0.2,
                                    ),
                                  ),
                                  onPressed: () async {
                                    try {
                                      if (isCheckedIn) {
                                        final notesCtrl = TextEditingController();
                                        final confirm = await showDialog<bool>(
                                          context: context,
                                          builder: (ctx) => AlertDialog(
                                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
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
                                                child: const Text('Cancel', style: TextStyle(color: Color(0xFF71717A))),
                                                onPressed: () => Navigator.pop(ctx, false),
                                              ),
                                              ElevatedButton(
                                                style: ElevatedButton.styleFrom(
                                                  backgroundColor: const Color(0xFF09090B),
                                                  foregroundColor: Colors.white,
                                                  minimumSize: const Size(100, 38),
                                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
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
                                          backgroundColor: const Color(0xFFDC2626),
                                          behavior: SnackBarBehavior.floating,
                                        ),
                                      );
                                    }
                                  },
                                ),
                              ),
                              if (isCheckedIn && att.checkinTime != null) ...[
                                const SizedBox(width: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF18181B), // Zinc 900
                                    borderRadius: BorderRadius.circular(10),
                                    border: Border.all(color: const Color(0xFF27272A)),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'STARTED',
                                        style: TextStyle(
                                          color: Color(0xFFA1A1AA),
                                          fontSize: 9,
                                          fontWeight: FontWeight.w700,
                                          letterSpacing: 0.5,
                                        ),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        DateFormatter.formatTime(att.checkinTime!),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 13,
                                          fontWeight: FontWeight.w700,
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
                    );
                  },
                  loading: () => Container(
                    height: 140,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFFE4E4E7)),
                    ),
                    child: const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
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
                const SizedBox(height: 24),

                // ── Overview Metrics Section ──────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Overview Metrics',
                      style: TextStyle(
                        color: Color(0xFF09090B),
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                        letterSpacing: -0.4,
                      ),
                    ),
                    TextButton.icon(
                      onPressed: () => context.go('/beat'),
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      icon: const Icon(Icons.arrow_forward_rounded, size: 14, color: Color(0xFF09090B)),
                      label: const Text(
                        'View Route',
                        style: TextStyle(
                          color: Color(0xFF09090B),
                          fontWeight: FontWeight.w700,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
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
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            value: syncCount == 0 ? 'Synced' : '$syncCount Pending',
                            label: 'Sync Status',
                            subtitle: syncCount == 0 ? 'All data up to date' : 'Requires network',
                            icon: syncCount == 0 ? Icons.cloud_done_rounded : Icons.cloud_upload_rounded,
                          ),
                        ),
                      ],
                    );
                  },
                  loading: () => const SizedBox(),
                  error: (_, __) => const SizedBox(),
                ),
                const SizedBox(height: 24),

                // ── Quick Operational Actions Grid ────────────────────────────
                const Text(
                  'Quick Actions',
                  style: TextStyle(
                    color: Color(0xFF09090B),
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                    letterSpacing: -0.4,
                  ),
                ),
                const SizedBox(height: 12),
                userAsync.when(
                  data: (user) {
                    final canAccessRestricted = user?.canAccessRestrictedModules ?? false;
                    return GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 1.35,
                      children: [
                        _buildActionTile(
                          context,
                          title: 'Record Payment',
                          subtitle: 'Cash & UPI entries',
                          icon: Icons.payments_outlined,
                          onTap: () => context.push('/payment/collect'),
                        ),
                        if (canAccessRestricted)
                          _buildActionTile(
                            context,
                            title: 'Log Expense',
                            subtitle: 'Claims & travel bills',
                            icon: Icons.receipt_long_outlined,
                            onTap: () => context.push('/expense'),
                          )
                        else
                          _buildActionTile(
                            context,
                            title: 'Create Order',
                            subtitle: 'Book customer order',
                            icon: Icons.add_shopping_cart_rounded,
                            onTap: () => context.push('/order/new'),
                          ),
                        if (canAccessRestricted)
                          _buildActionTile(
                            context,
                            title: 'Material Request',
                            subtitle: 'Stock & POSM allocation',
                            icon: Icons.inventory_2_outlined,
                            onTap: () => context.push('/material-request'),
                          )
                        else
                          _buildActionTile(
                            context,
                            title: 'Beat Plan',
                            subtitle: 'Today\'s route outlets',
                            icon: Icons.map_outlined,
                            onTap: () => context.go('/beat'),
                          ),
                        _buildActionTile(
                          context,
                          title: 'Asset Deploy',
                          subtitle: 'Equipment & coolers',
                          icon: Icons.build_circle_outlined,
                          onTap: () => context.push('/asset-cap'),
                        ),
                      ],
                    );
                  },
                  loading: () => const SizedBox(),
                  error: (_, __) => const SizedBox(),
                ),
                const SizedBox(height: 20),
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
    Color color = const Color(0xFF09090B),
  }) {
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0), // Zinc 200
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 6,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: IconButton(
        padding: EdgeInsets.zero,
        icon: Icon(icon, color: color, size: 18),
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
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0), // Zinc 200
        boxShadow: const [
          BoxShadow(
            color: Color(0x06000000),
            blurRadius: 10,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F4F5), // Zinc 100
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0),
                ),
                child: Icon(icon, color: const Color(0xFF09090B), size: 18),
              ),
              Container(
                width: 6,
                height: 6,
                decoration: const BoxDecoration(
                  color: Color(0xFF09090B),
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            value,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: Color(0xFF09090B),
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: Color(0xFF18181B),
            ),
          ),
          const SizedBox(height: 1),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w500,
              color: Color(0xFF71717A),
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
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0), // Zinc 200
            boxShadow: const [
              BoxShadow(
                color: Color(0x06000000),
                blurRadius: 8,
                offset: Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F4F5), // Zinc 100
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0),
                ),
                child: Icon(icon, color: const Color(0xFF09090B), size: 18),
              ),
              const SizedBox(height: 10),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF09090B),
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF71717A),
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
