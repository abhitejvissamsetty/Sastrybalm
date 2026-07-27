import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../utils/date_formatter.dart';

final myTimesheetsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final client = ref.watch(apiClientProvider);
  final res = await client.dio.get('/timesheets/my-timesheets');
  return res.data['items'] as List;
});

class TimesheetScreen extends ConsumerStatefulWidget {
  const TimesheetScreen({super.key});

  @override
  ConsumerState<TimesheetScreen> createState() => _TimesheetScreenState();
}

class _TimesheetScreenState extends ConsumerState<TimesheetScreen> {
  @override
  Widget build(BuildContext context) {
    final attendanceAsync = ref.watch(attendanceProvider);
    final timesheetsAsync = ref.watch(myTimesheetsProvider);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('My Timesheets & Working Hours'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(attendanceProvider.notifier).refresh();
              ref.refresh(myTimesheetsProvider);
            },
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: const Color(0xFF09090B),
          onRefresh: () async {
            await ref.read(attendanceProvider.notifier).refresh();
            return ref.refresh(myTimesheetsProvider);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Working Hours Today Hero Card ─────────────────────────────
                attendanceAsync.when(
                  data: (att) {
                    final isCheckedIn = att.checkedIn && att.isOpen;
                    return Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF09090B), // Zinc 950
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: const Color(0xFF27272A)),
                        boxShadow: const [
                          BoxShadow(color: Color(0x1F000000), blurRadius: 16, offset: Offset(0, 6)),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                'TODAY\'S TIMESHEET SHIFT',
                                style: TextStyle(
                                  color: Color(0xFFA1A1AA),
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.8,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: isCheckedIn ? const Color(0xFF15803D) : const Color(0xFF27272A),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Text(
                                  isCheckedIn ? 'ACTIVE SHIFT' : 'INACTIVE',
                                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            isCheckedIn && att.checkinTime != null
                                ? 'Shift Checked In at ${DateFormatter.formatTime(att.checkinTime!)}'
                                : 'No active timesheet shift today',
                            style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Customer Outlet Visits Logged: ${att.visitCount}',
                            style: const TextStyle(color: Color(0xFFA1A1AA), fontSize: 13),
                          ),
                        ],
                      ),
                    );
                  },
                  loading: () => const SizedBox(),
                  error: (_, __) => const SizedBox(),
                ),
                const SizedBox(height: 24),

                const Text(
                  'Synced Timesheets & Work Logs',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Color(0xFF09090B)),
                ),
                const SizedBox(height: 12),

                timesheetsAsync.when(
                  data: (items) {
                    if (items.isEmpty) {
                      return Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFFE4E4E7)),
                        ),
                        child: const Center(
                          child: Text(
                            'No timesheets logged yet. Begin a workday shift on Home to log your first timesheet.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Color(0xFF71717A), fontSize: 13),
                          ),
                        ),
                      );
                    }

                    return ListView.separated(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (ctx, i) {
                        final ts = items[i];
                        final checkinStr = ts['checkin_time'] != null
                            ? DateFormatter.formatTime(DateTime.parse(ts['checkin_time']))
                            : 'N/A';
                        final checkoutStr = ts['checkout_time'] != null
                            ? DateFormatter.formatTime(DateTime.parse(ts['checkout_time']))
                            : 'In Progress';
                        final workDateStr = DateFormatter.formatDate(DateTime.parse(ts['work_date']));
                        final approval = (ts['approval_status'] ?? 'pending').toString().toUpperCase();

                        return Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: const Color(0xFFE4E4E7)),
                            boxShadow: const [
                              BoxShadow(color: Color(0x04000000), blurRadius: 6, offset: Offset(0, 2)),
                            ],
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(workDateStr, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF09090B))),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: approval == 'APPROVED' ? const Color(0xFFDCFCE7) : const Color(0xFFFEF3C7),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      approval,
                                      style: TextStyle(
                                        color: approval == 'APPROVED' ? const Color(0xFF15803D) : const Color(0xFFD97706),
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text('Check-in: $checkinStr', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
                                  Text('Check-out: $checkoutStr', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text('Hours Worked: ${ts['hours_worked']} hrs', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF09090B))),
                                  Text('Outlet Visits: ${ts['visit_count']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF09090B))),
                                ],
                              ),
                            ],
                          ),
                        );
                      },
                    );
                  },
                  loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
                  error: (e, __) => Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
                    child: Text('Error loading timesheets: $e', style: const TextStyle(color: Colors.red)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
