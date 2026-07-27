import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/sync_provider.dart';
import '../../models/attendance.dart';
import '../../widgets/gps_status_chip.dart';
import '../../utils/date_formatter.dart';

class DashboardTab extends ConsumerWidget {
  const DashboardTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(authStateProvider);
    final attendanceAsync = ref.watch(attendanceProvider);
    final syncCount = ref.watch(syncProvider);
    final attendance = attendanceAsync.value ?? AttendanceState.notCheckedIn();
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

                // ── Sleek Workday Hero Card (shadcn Dark Zinc) ────────────────
                Container(
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
                                    color: Colors.white,
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
                        style: const TextStyle(
                          color: Colors.white,
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
                          if (!isCheckedIn) ...[
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
                                    DateFormatter.formatTime(attendance.checkinTime!),
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
                ),
                const SizedBox(height: 24),

                // ── Workday Gateway / Active Operations Section ───────────────
                if (!isCheckedIn) ...[
                  // ── Inactive Workday Action Center ─────────────────────────
                  const Text(
                    'Workday Action Center',
                    style: TextStyle(
                      color: Color(0xFF09090B),
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                      letterSpacing: -0.4,
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildActionCard(
                    context,
                    title: 'Apply for Time-Off / Leave',
                    description: 'Request planned leave or casual time off. Submitted requests will be routed to your TM for approval.',
                    icon: Icons.event_note_outlined,
                    buttonLabel: 'Open Leave Form',
                    isPrimary: false,
                    onTap: () => context.push('/leave/apply'),
                  ),
                ] else ...[
                  // ── Active Workday Operations ────────────────────────────────
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
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (isL2Plus) ...[
                            // ── Row 1: Start Retailing + Joint Working ──────────
                            Row(
                              children: [
                                Expanded(
                                  child: _buildActionTile(
                                    context,
                                    title: 'Start Retailing',
                                    subtitle: 'Secondary beat orders',
                                    icon: Icons.storefront_rounded,
                                    onTap: () => context.push('/beat'),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: _buildActionTile(
                                    context,
                                    title: 'Joint Working',
                                    subtitle: 'Subordinate visits',
                                    icon: Icons.people_alt_rounded,
                                    onTap: () => context.push('/joint-working'),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            // ── Row 2: Create Primary (full width) ─────────────
                            _buildActionCard(
                              context,
                              title: 'Create Primary',
                              description: 'Book primary distributor & channel partner order.',
                              icon: Icons.receipt_long_rounded,
                              buttonLabel: 'Create Primary Order Now',
                              isPrimary: true,
                              onTap: () => context.push('/order/new'),
                            ),
                            const SizedBox(height: 12),
                            // ── Row 3: Apply Leave (full width) ────────────────
                            _buildFullWidthTile(
                              context,
                              title: 'Apply Leave',
                              subtitle: 'Submit time-off requests for approval',
                              icon: Icons.event_available_rounded,
                              onTap: () => context.push('/leave/apply'),
                            ),
                          ] else ...[
                            // ── Non-L2: original grid layout ───────────────────
                            GridView.count(
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
                                  onTap: () => context.push('/beat'),
                                ),
                                _buildActionTile(
                                  context,
                                  title: 'Apply Leave',
                                  subtitle: 'Time off requests',
                                  icon: Icons.event_available_rounded,
                                  onTap: () => context.push('/leave/apply'),
                                ),
                                if (user?.role == 'qc_manager')
                                  _buildActionTile(
                                    context,
                                    title: 'QC Inspection',
                                    subtitle: 'Batch ID & Inspection',
                                    icon: Icons.verified_rounded,
                                    onTap: () => context.push('/procurement/qc'),
                                  ),
                                if (user?.role == 'vendor_admin')
                                  _buildActionTile(
                                    context,
                                    title: 'Vendor Admin Portal',
                                    subtitle: 'Quotations & Work Orders',
                                    icon: Icons.corporate_fare_rounded,
                                    onTap: () => context.push('/procurement/vendor-admin'),
                                  ),
                                if (user?.role == 'vendor_technician')
                                  _buildActionTile(
                                    context,
                                    title: 'Vendor Tech Portal',
                                    subtitle: 'Recce & Asset Installs',
                                    icon: Icons.build_circle_rounded,
                                    onTap: () => context.push('/procurement/vendor-tech'),
                                  ),
                              ],
                            ),
                          ],
                        ],
                      );
                    },
                    loading: () => const SizedBox(),
                    error: (_, __) => const SizedBox(),
                  ),
                ],
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
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE4E4E7)),
        boxShadow: const [
          BoxShadow(color: Color(0x04000000), blurRadius: 8, offset: Offset(0, 2)),
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
                  color: isPrimary ? const Color(0xFF09090B) : const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: isPrimary ? Colors.white : const Color(0xFF09090B), size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF09090B)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            description,
            style: const TextStyle(color: Color(0xFF71717A), fontSize: 13, height: 1.4),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: isPrimary
                ? ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF09090B),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: onTap,
                    child: Text(buttonLabel, style: const TextStyle(fontWeight: FontWeight.bold)),
                  )
                : OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF09090B),
                      side: const BorderSide(color: Color(0xFFE4E4E7)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
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
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE4E4E7), width: 1),
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
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
                    child: Icon(icon, size: 20, color: const Color(0xFF09090B)),
                  ),
                  const Icon(Icons.arrow_forward_ios_rounded, size: 12, color: Color(0xFFA1A1AA)),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Color(0xFF09090B),
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                      letterSpacing: -0.2,
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
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE4E4E7), width: 1),
            boxShadow: const [
              BoxShadow(
                color: Color(0x04000000),
                blurRadius: 6,
                offset: Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, size: 20, color: const Color(0xFF09090B)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Color(0xFF09090B),
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: Color(0xFF71717A),
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFFA1A1AA)),
            ],
          ),
        ),
      ),
    );
  }
}
