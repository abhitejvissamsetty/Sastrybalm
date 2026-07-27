import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/sync_provider.dart';
import '../../providers/beat_provider.dart';
import '../../models/attendance.dart';
import '../../models/outlet.dart';
import '../../widgets/gps_status_chip.dart';
import '../../utils/date_formatter.dart';

class DashboardTab extends ConsumerWidget {
  const DashboardTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(authStateProvider);
    final user = userAsync.valueOrNull;
    final attendanceAsync = ref.watch(attendanceProvider);
    final syncCount = ref.watch(syncProvider);
    final attendance = attendanceAsync.valueOrNull ?? AttendanceState.notCheckedIn();
    final isCheckedIn = attendance.checkedIn && attendance.isOpen;

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA), // Zinc 50
      body: SafeArea(
        child: RefreshIndicator(
          color: const Color(0xFF09090B),
          onRefresh: () async {
            await ref.read(attendanceProvider.notifier).refresh();
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
                            backgroundColor: Color(0xFF09090B),
                            child: Icon(Icons.person_rounded, color: Colors.white, size: 20),
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
                                    color: Color(0xFF09090B),
                                    fontWeight: FontWeight.w800,
                                    fontSize: 19,
                                    letterSpacing: -0.5,
                                  ),
                                );
                              },
                              loading: () => const Text('Hi, Sales Rep', style: TextStyle(color: Color(0xFF09090B), fontWeight: FontWeight.bold, fontSize: 19)),
                              error: (_, __) => const Text('Hi, Sales Rep', style: TextStyle(color: Color(0xFF09090B), fontWeight: FontWeight.bold, fontSize: 19)),
                            ),
                            const SizedBox(height: 2),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF4F4F5),
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
                          color: const Color(0xFFDC2626),
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

                // ── Dynamic Workday Hero Card (Reversed: Black/White -> White/Black Inversion) ──
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: isCheckedIn ? Colors.white : const Color(0xFF09090B),
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: isCheckedIn ? const Color(0xFFE4E4E7) : const Color(0xFF27272A),
                      width: 1,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: isCheckedIn ? const Color(0x05000000) : const Color(0x1F000000),
                        blurRadius: 16,
                        offset: const Offset(0, 6),
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
                              color: isCheckedIn ? const Color(0xFFF4F4F5) : const Color(0xFF18181B),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: isCheckedIn ? const Color(0xFFE4E4E7) : const Color(0xFF27272A),
                                width: 1,
                              ),
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
                                  style: TextStyle(
                                    color: isCheckedIn ? const Color(0xFF09090B) : Colors.white,
                                    fontSize: 10,
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
                      const SizedBox(height: 16),
                      Text(
                        isCheckedIn ? 'Shift In Progress' : 'Ready to Start Your Shift?',
                        style: TextStyle(
                          color: isCheckedIn ? const Color(0xFF09090B) : Colors.white,
                          fontSize: 21,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        isCheckedIn
                            ? 'Your shift check-in is confirmed. Beat route tracking & order booking are active.'
                            : 'Begin your workday shift with GPS location verification or submit a leave request.',
                        style: TextStyle(
                          color: isCheckedIn ? const Color(0xFF71717A) : const Color(0xFFA1A1AA),
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
                                backgroundColor: isCheckedIn ? const Color(0xFF09090B) : Colors.white,
                                foregroundColor: isCheckedIn ? Colors.white : const Color(0xFF09090B),
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
                                color: isCheckedIn ? Colors.white : const Color(0xFF09090B),
                              ),
                              label: Text(
                                isCheckedIn ? 'End Workday' : 'Begin Workday',
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
                                    _showBeginWorkdayModal(context, ref);
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
                          if (!isCheckedIn && user?.role != 'vendor_admin' && user?.role != 'vendor_technician') ...[
                            const SizedBox(width: 10),
                            OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                foregroundColor: Colors.white,
                                side: const BorderSide(color: Color(0xFF3F3F46)),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                minimumSize: const Size(120, 46),
                              ),
                              icon: const Icon(Icons.event_note_outlined, size: 16, color: Colors.white),
                              label: const Text(
                                'Apply Leave',
                                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                              ),
                              onPressed: () => context.push('/leave/apply'),
                            ),
                          ] else if (attendance.checkinTime != null) ...[
                            const SizedBox(width: 10),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF4F4F5),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: const Color(0xFFE4E4E7)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'STARTED',
                                    style: TextStyle(
                                      color: Color(0xFF71717A),
                                      fontSize: 9,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    DateFormatter.formatTime(attendance.checkinTime!),
                                    style: const TextStyle(
                                      color: Color(0xFF09090B),
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
                ),
                const SizedBox(height: 24),

                // ── Workday Quick Actions (Dynamic Color Inversion) ───────────
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
                    final isL2Plus = user?.isL2OrAbove ?? false;
                    if (isL2Plus) {
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: _buildActionTile(
                                  context,
                                  title: 'Start Retailing',
                                  subtitle: 'Secondary beat orders',
                                  icon: Icons.storefront_rounded,
                                  isDark: isCheckedIn,
                                  onTap: () => _showStartRetailingDrawer(context, ref),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: _buildActionTile(
                                  context,
                                  title: 'Joint Working',
                                  subtitle: 'Subordinate visits',
                                  icon: Icons.people_alt_rounded,
                                  isDark: isCheckedIn,
                                  onTap: () => context.push('/joint-working'),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          _buildActionCard(
                            context,
                            title: 'Create Primary',
                            description: 'Book primary distributor & channel partner order.',
                            icon: Icons.receipt_long_rounded,
                            buttonLabel: 'Create Primary Order Now',
                            isPrimary: true,
                            isDark: false,
                            onTap: () => context.push('/order/new'),
                          ),
                          const SizedBox(height: 12),
                          if (user?.role != 'vendor_admin' && user?.role != 'vendor_technician')
                            _buildFullWidthTile(
                              context,
                              title: 'Apply Leave',
                              subtitle: 'Submit time-off requests for approval',
                              icon: Icons.event_available_rounded,
                              isDark: false,
                              onTap: () => context.push('/leave/apply'),
                            ),
                        ],
                      );
                    }
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
                          title: 'Start Retailing',
                          subtitle: 'Secondary beat orders',
                          icon: Icons.storefront_rounded,
                          isDark: isCheckedIn,
                          onTap: () => _showStartRetailingDrawer(context, ref),
                        ),
                        if (user?.role != 'vendor_admin' && user?.role != 'vendor_technician')
                          _buildActionTile(
                            context,
                            title: 'Apply Leave',
                            subtitle: 'Time off requests',
                            icon: Icons.event_available_rounded,
                            isDark: isCheckedIn,
                            onTap: () => context.push('/leave/apply'),
                          ),
                        if (user?.role == 'qc_manager')
                          _buildActionTile(
                            context,
                            title: 'QC Inspection',
                            subtitle: 'Batch ID & Inspection',
                            icon: Icons.verified_rounded,
                            isDark: isCheckedIn,
                            onTap: () => context.push('/procurement/qc'),
                          ),
                        if (user?.role == 'vendor_admin')
                          _buildActionTile(
                            context,
                            title: 'Vendor Admin Portal',
                            subtitle: 'Quotations & Work Orders',
                            icon: Icons.corporate_fare_rounded,
                            isDark: isCheckedIn,
                            onTap: () => context.push('/procurement/vendor-admin'),
                          ),
                        if (user?.role == 'vendor_technician')
                          _buildActionTile(
                            context,
                            title: 'Vendor Tech Portal',
                            subtitle: 'Recce & Asset Installs',
                            icon: Icons.build_circle_rounded,
                            isDark: isCheckedIn,
                            onTap: () => context.push('/procurement/vendor-tech'),
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

  void _showBeginWorkdayModal(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          bool isLoading = false;
          return Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 36,
                    height: 4,
                    decoration: BoxDecoration(
                      color: const Color(0xFFE4E4E7),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: const Color(0xFF09090B),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.play_circle_fill_rounded, color: Colors.white, size: 24),
                    ),
                    const SizedBox(width: 14),
                    const Expanded(
                      child: Text(
                        '1. Begin Workday Shift',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF09090B),
                          letterSpacing: -0.4,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                const Text(
                  'Verify your GPS location and start your sales shift to unlock outlet visits and order entry.',
                  style: TextStyle(
                    color: Color(0xFF71717A),
                    fontSize: 14,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF09090B),
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 50),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 0,
                    ),
                    onPressed: isLoading
                        ? null
                        : () async {
                            setModalState(() => isLoading = true);
                            try {
                              await ref.read(attendanceProvider.notifier).checkIn();
                              if (ctx.mounted) {
                                Navigator.pop(ctx);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Workday shift started successfully!'),
                                    backgroundColor: Color(0xFF22C55E),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              }
                            } catch (e) {
                              if (ctx.mounted) {
                                setModalState(() => isLoading = false);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('Failed to check in: ${e.toString().replaceAll('Exception:', '')}'),
                                    backgroundColor: const Color(0xFFDC2626),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              }
                            }
                          },
                    child: isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text(
                            'Start Shift Now',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
            ),
          );
        },
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
        border: Border.all(color: const Color(0xFFE4E4E7), width: 1.0),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 6,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: IconButton(
        icon: Icon(icon, size: 18, color: color),
        tooltip: tooltip,
        padding: EdgeInsets.zero,
        onPressed: onTap,
      ),
    );
  }

  Widget _buildActionCard(
    BuildContext context, {
    required String title,
    required String description,
    required IconData icon,
    required String buttonLabel,
    required bool isPrimary,
    required VoidCallback onTap,
    bool isDark = false,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF09090B) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? const Color(0xFF27272A) : const Color(0xFFE4E4E7)),
        boxShadow: [
          BoxShadow(
            color: isDark ? const Color(0x1F000000) : const Color(0x04000000),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF18181B)
                      : (isPrimary ? const Color(0xFF09090B) : const Color(0xFFF4F4F5)),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  icon,
                  color: isDark ? Colors.white : (isPrimary ? Colors.white : const Color(0xFF09090B)),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                    color: isDark ? Colors.white : const Color(0xFF09090B),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            description,
            style: TextStyle(
              color: isDark ? const Color(0xFFA1A1AA) : const Color(0xFF71717A),
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: isDark ? Colors.white : const Color(0xFF09090B),
                foregroundColor: isDark ? const Color(0xFF09090B) : Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 0,
              ),
              onPressed: onTap,
              child: Text(buttonLabel, style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
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
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE4E4E7), width: 1),
        boxShadow: const [
          BoxShadow(
            color: Color(0x05000000),
            blurRadius: 8,
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
                  color: const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, size: 18, color: const Color(0xFF09090B)),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            value,
            style: const TextStyle(
              color: Color(0xFF09090B),
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFF09090B),
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: const TextStyle(
              color: Color(0xFF71717A),
              fontSize: 11,
              fontWeight: FontWeight.w500,
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
    bool isDark = false,
  }) {
    return Material(
      color: isDark ? const Color(0xFF09090B) : Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? const Color(0xFF27272A) : const Color(0xFFE4E4E7),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: isDark ? const Color(0x1F000000) : const Color(0x04000000),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF18181B) : const Color(0xFFF4F4F5),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon, size: 20, color: isDark ? Colors.white : const Color(0xFF09090B)),
                  ),
                  Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 12,
                    color: isDark ? const Color(0xFF71717A) : const Color(0xFFA1A1AA),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: isDark ? Colors.white : const Color(0xFF09090B),
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                      letterSpacing: -0.2,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: isDark ? const Color(0xFFA1A1AA) : const Color(0xFF71717A),
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFullWidthTile(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required VoidCallback onTap,
    bool isDark = false,
  }) {
    return Material(
      color: isDark ? const Color(0xFF09090B) : Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? const Color(0xFF27272A) : const Color(0xFFE4E4E7),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: isDark ? const Color(0x1F000000) : const Color(0x04000000),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF18181B) : const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, size: 20, color: isDark ? Colors.white : const Color(0xFF09090B)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: isDark ? Colors.white : const Color(0xFF09090B),
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? const Color(0xFFA1A1AA) : const Color(0xFF71717A),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.arrow_forward_ios_rounded,
                size: 14,
                color: isDark ? const Color(0xFF71717A) : const Color(0xFFA1A1AA),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showStartRetailingDrawer(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      enableDrag: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _StartRetailingBottomSheet(ref: ref),
    );
  }
}

class _StartRetailingBottomSheet extends ConsumerStatefulWidget {
  final WidgetRef ref;
  const _StartRetailingBottomSheet({required this.ref});

  @override
  ConsumerState<_StartRetailingBottomSheet> createState() => _StartRetailingBottomSheetState();
}

class _StartRetailingBottomSheetState extends ConsumerState<_StartRetailingBottomSheet> {
  final _searchCtrl = TextEditingController();
  String _searchQuery = '';

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final beatsAsync = ref.watch(beatsProvider);

    return Container(
      height: MediaQuery.of(context).size.height * 0.80,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Drag indicator bar
          const SizedBox(height: 12),
          Container(
            width: 44,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFD4D4D8),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 16),
          // Drawer Title
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text(
                      'Start Retailing',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF09090B),
                        letterSpacing: -0.4,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Active beats mapped to L1 position hierarchy',
                      style: TextStyle(
                        fontSize: 12,
                        color: Color(0xFF71717A),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded, color: Color(0xFF71717A)),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Search Input Bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: TextField(
              controller: _searchCtrl,
              onChanged: (val) => setState(() => _searchQuery = val.trim().toLowerCase()),
              decoration: InputDecoration(
                hintText: 'Search by beat name, code, position or rep...',
                hintStyle: const TextStyle(fontSize: 13, color: Color(0xFFA1A1AA)),
                prefixIcon: const Icon(Icons.search_rounded, color: Color(0xFF71717A), size: 20),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear_rounded, size: 18),
                        onPressed: () {
                          _searchCtrl.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(vertical: 12),
                filled: true,
                fillColor: const Color(0xFFF4F4F5),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Divider(height: 1, color: Color(0xFFE4E4E7)),
          // Active Beats Vertical List
          Expanded(
            child: beatsAsync.when(
              data: (beats) {
                final filtered = beats.where((b) {
                  if (_searchQuery.isEmpty) return true;
                  final nameMatch = b.name.toLowerCase().contains(_searchQuery);
                  final codeMatch = b.code.toLowerCase().contains(_searchQuery);
                  final posMatch = (b.l1PositionName ?? '').toLowerCase().contains(_searchQuery);
                  final userMatch = (b.assignedUserName ?? '').toLowerCase().contains(_searchQuery);
                  return nameMatch || codeMatch || posMatch || userMatch;
                }).toList();

                if (filtered.isEmpty) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: const [
                          Icon(Icons.search_off_rounded, size: 48, color: Color(0xFFA1A1AA)),
                          SizedBox(height: 12),
                          Text(
                            'No active beats found',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF09090B)),
                          ),
                          SizedBox(height: 4),
                          Text(
                            'Try adjusting your search or check L1 position mappings.',
                            textAlign: TextAlign.center,
                            style: TextStyle(fontSize: 12, color: Color(0xFF71717A)),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                return ListView.separated(
                  padding: const EdgeInsets.all(20),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (ctx, i) {
                    final beat = filtered[i];
                    return Material(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                      child: InkWell(
                        onTap: () {
                          ref.read(selectedBeatIdProvider.notifier).state = beat.id;
                          Navigator.pop(ctx);
                          context.push('/beat');
                        },
                        borderRadius: BorderRadius.circular(14),
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: const Color(0xFFE4E4E7)),
                            boxShadow: const [
                              BoxShadow(
                                color: Color(0x04000000),
                                blurRadius: 6,
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
                                  Expanded(
                                    child: Text(
                                      beat.name,
                                      style: const TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w700,
                                        color: Color(0xFF09090B),
                                      ),
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFF4F4F5),
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(color: const Color(0xFFE4E4E7)),
                                    ),
                                    child: Text(
                                      beat.code,
                                      style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w700,
                                        color: Color(0xFF3F3F46),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              // Line 1 under Beat Title: L1 Position
                              Row(
                                children: [
                                  const Icon(Icons.account_tree_outlined, size: 14, color: Color(0xFF71717A)),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      'Position: ${beat.l1PositionName ?? "L1 Territory Field Position"}',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: Color(0xFF52525B),
                                        fontWeight: FontWeight.w500,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              // Line 2 under Beat Title: Assigned User
                              Row(
                                children: [
                                  const Icon(Icons.person_outline_rounded, size: 14, color: Color(0xFF71717A)),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      'Assigned User: ${beat.assignedUserName ?? "Unassigned Rep"}',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: Color(0xFF52525B),
                                        fontWeight: FontWeight.w500,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              const Divider(height: 1, color: Color(0xFFF4F4F5)),
                              const SizedBox(height: 8),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFEFF6FF),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.storefront_rounded, size: 13, color: Color(0xFF2563EB)),
                                        const SizedBox(width: 4),
                                        Text(
                                          '${beat.activeOutletCount} Outlets',
                                          style: const TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w700,
                                            color: Color(0xFF2563EB),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Row(
                                    children: const [
                                      Text(
                                        'Select Route',
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w700,
                                          color: Color(0xFF09090B),
                                        ),
                                      ),
                                      SizedBox(width: 4),
                                      Icon(Icons.arrow_forward_ios_rounded, size: 12, color: Color(0xFF09090B)),
                                    ],
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
              error: (e, _) => Center(child: Text('Failed to load beats: $e')),
            ),
          ),
        ],
      ),
    );
  }
}

