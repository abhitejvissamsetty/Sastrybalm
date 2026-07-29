import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';
import '../../services/operations_service.dart';

class LeaveApplyScreen extends ConsumerStatefulWidget {
  const LeaveApplyScreen({super.key});

  @override
  ConsumerState<LeaveApplyScreen> createState() => _LeaveApplyScreenState();
}

class _LeaveApplyScreenState extends ConsumerState<LeaveApplyScreen> {
  final _reasonCtrl = TextEditingController();
  String _selectedType = 'casual';
  DateTime _leaveDate = DateTime.now().add(const Duration(days: 1));
  String _leaveDuration = 'full'; // 'full' or 'half'
  String _halfDaySession = 'first_half'; // 'first_half' or 'second_half'

  bool _loading = false;
  List<dynamic> _leaveHistory = [];

  @override
  void initState() {
    super.initState();
    _fetchHistory();
  }

  Future<void> _fetchHistory() async {
    try {
      final client = ref.read(apiClientProvider);
      final service = LeaveService(client);
      final history = await service.getMyLeaves();
      if (mounted) {
        setState(() => _leaveHistory = history);
      }
    } catch (_) {}
  }

  Future<void> _submitLeave() async {
    final userReason = _reasonCtrl.text.trim();
    if (userReason.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a reason for your leave.')),
      );
      return;
    }

    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final service = LeaveService(client);
      final formattedDate = _leaveDate.toIso8601String().split('T')[0];

      String fullReason = userReason;
      if (_leaveDuration == 'half') {
        final sessionLabel = _halfDaySession == 'first_half'
            ? 'First Half (Morning)'
            : 'Second Half (Afternoon)';
        fullReason = '[Half Day - $sessionLabel] $userReason';
      }

      await service.applyLeave(
        leaveType: _selectedType,
        startDate: formattedDate,
        endDate: formattedDate,
        duration: _leaveDuration,
        halfDaySession: _leaveDuration == 'half' ? _halfDaySession : null,
        reason: fullReason,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Leave application submitted successfully!')),
        );
        _reasonCtrl.clear();
        _fetchHistory();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _reasonCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final formattedLeaveDate = _leaveDate.toIso8601String().split('T')[0];

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('Apply for Leave',
            style: TextStyle(
                fontWeight: FontWeight.bold, color: Color(0xFF09090B))),
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF09090B)),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'New Leave Application',
              style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF09090B)),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFFE4E4E7)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: _selectedType,
                    decoration: const InputDecoration(
                      labelText: 'Leave Type',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(
                          value: 'casual', child: Text('Casual Leave')),
                      DropdownMenuItem(
                          value: 'sick', child: Text('Sick Leave')),
                      DropdownMenuItem(
                          value: 'earned', child: Text('Earned Leave')),
                      DropdownMenuItem(
                          value: 'unpaid', child: Text('Unpaid Leave')),
                    ],
                    onChanged: (val) {
                      if (val != null) setState(() => _selectedType = val);
                    },
                  ),
                  const SizedBox(height: 14),

                  // Leave Duration Segmented Selection (Full Day / Half Day)
                  const Text('Leave Duration',
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF52525B))),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: InkWell(
                          onTap: () => setState(() => _leaveDuration = 'full'),
                          borderRadius: BorderRadius.circular(10),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 150),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            decoration: BoxDecoration(
                              color: _leaveDuration == 'full'
                                  ? const Color(0xFF09090B)
                                  : const Color(0xFFF4F4F5),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: _leaveDuration == 'full'
                                    ? const Color(0xFF09090B)
                                    : const Color(0xFFE4E4E7),
                              ),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.wb_sunny_rounded,
                                  size: 16,
                                  color: _leaveDuration == 'full'
                                      ? Colors.white
                                      : const Color(0xFF71717A),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Full Day',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                    color: _leaveDuration == 'full'
                                        ? Colors.white
                                        : const Color(0xFF3F3F46),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: InkWell(
                          onTap: () => setState(() => _leaveDuration = 'half'),
                          borderRadius: BorderRadius.circular(10),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 150),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            decoration: BoxDecoration(
                              color: _leaveDuration == 'half'
                                  ? const Color(0xFF09090B)
                                  : const Color(0xFFF4F4F5),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: _leaveDuration == 'half'
                                    ? const Color(0xFF09090B)
                                    : const Color(0xFFE4E4E7),
                              ),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.brightness_medium_rounded,
                                  size: 16,
                                  color: _leaveDuration == 'half'
                                      ? Colors.white
                                      : const Color(0xFF71717A),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Half Day',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                    color: _leaveDuration == 'half'
                                        ? Colors.white
                                        : const Color(0xFF3F3F46),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),

                  // Half Day Session Options (if Half Day selected)
                  if (_leaveDuration == 'half') ...[
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _halfDaySession,
                      decoration: const InputDecoration(
                        labelText: 'Half Day Session',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.access_time_rounded,
                            size: 18, color: Color(0xFF2563EB)),
                      ),
                      items: const [
                        DropdownMenuItem(
                            value: 'first_half',
                            child: Text('First Half (Morning)')),
                        DropdownMenuItem(
                            value: 'second_half',
                            child: Text('Second Half (Afternoon)')),
                      ],
                      onChanged: (val) {
                        if (val != null) setState(() => _halfDaySession = val);
                      },
                    ),
                  ],

                  const SizedBox(height: 14),

                  // Single Day Leave Date Picker
                  InkWell(
                    onTap: () async {
                      final picked = await showDatePicker(
                        context: context,
                        initialDate: _leaveDate,
                        firstDate: DateTime.now(),
                        lastDate: DateTime.now().add(const Duration(days: 90)),
                      );
                      if (picked != null) setState(() => _leaveDate = picked);
                    },
                    borderRadius: BorderRadius.circular(8),
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Leave Date',
                        prefixIcon: Icon(Icons.calendar_today_rounded,
                            size: 18, color: Color(0xFF2563EB)),
                        border: OutlineInputBorder(),
                      ),
                      child: Text(
                        formattedLeaveDate,
                        style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            color: Color(0xFF09090B)),
                      ),
                    ),
                  ),

                  const SizedBox(height: 14),
                  TextField(
                    controller: _reasonCtrl,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Reason',
                      hintText: 'e.g. Family function or medical checkup',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 18),
                  SizedBox(
                    width: double.infinity,
                    height: 46,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF09090B),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: _loading ? null : _submitLeave,
                      child: _loading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  color: Colors.white, strokeWidth: 2))
                          : const Text('Submit Application',
                              style: TextStyle(
                                  fontWeight: FontWeight.bold, fontSize: 14)),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 28),
            const Text(
              'My Leave History',
              style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF09090B)),
            ),
            const SizedBox(height: 14),
            if (_leaveHistory.isEmpty)
              const Text('No leave records found.',
                  style: TextStyle(color: Color(0xFF71717A)))
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _leaveHistory.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (ctx, i) {
                  final item = _leaveHistory[i];
                  final isSameDate = item['start_date'] == item['end_date'];
                  final dateDisplay = isSameDate
                      ? '${item['start_date']}'
                      : '${item['start_date']} to ${item['end_date']}';
                  final reasonText = item['reason'] ?? '';

                  return Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFE4E4E7)),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    '${item['leave_type'].toString().toUpperCase()} LEAVE',
                                    style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 13,
                                        color: Color(0xFF09090B)),
                                  ),
                                  if (reasonText
                                      .toString()
                                      .contains('[Half Day')) ...[
                                    const SizedBox(width: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 6, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFFEF3C7),
                                        borderRadius: BorderRadius.circular(4),
                                        border: Border.all(
                                            color: const Color(0xFFFDE68A)),
                                      ),
                                      child: const Text(
                                        'HALF DAY',
                                        style: TextStyle(
                                            fontSize: 9,
                                            fontWeight: FontWeight.w800,
                                            color: Color(0xFFB45309)),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  const Icon(Icons.event_rounded,
                                      size: 14, color: Color(0xFF71717A)),
                                  const SizedBox(width: 4),
                                  Text(
                                    dateDisplay,
                                    style: const TextStyle(
                                        color: Color(0xFF71717A),
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600),
                                  ),
                                ],
                              ),
                              if (reasonText.toString().isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Text(
                                  reasonText,
                                  style: const TextStyle(
                                      fontSize: 11, color: Color(0xFF52525B)),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF4F4F5),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: const Color(0xFFE4E4E7)),
                          ),
                          child: Text(
                            item['status'].toString().toUpperCase(),
                            style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF3F3F46)),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
}
