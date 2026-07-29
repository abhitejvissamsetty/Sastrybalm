import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/attendance.dart';
import '../../providers/beat_provider.dart';
import '../../providers/visit_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../services/attendance_service.dart';

class OutletDetailScreen extends ConsumerStatefulWidget {
  final int outletId;

  const OutletDetailScreen({super.key, required this.outletId});

  @override
  ConsumerState<OutletDetailScreen> createState() => _OutletDetailScreenState();
}

class _OutletDetailScreenState extends ConsumerState<OutletDetailScreen> {
  Timer? _timer;
  Duration _elapsed = Duration.zero;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _startTimerIfNeeded();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startTimerIfNeeded() {
    final activeVisits = ref.read(activeVisitProvider);
    final visit = activeVisits[widget.outletId];
    if (visit != null) {
      _timer?.cancel();
      setState(() {
        _elapsed = DateTime.now().difference(visit.visitTime);
      });
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        setState(() {
          _elapsed = DateTime.now().difference(visit.visitTime);
        });
      });
    }
  }

  Future<void> _showAssetActions() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Wrap(children: [
          const ListTile(
              title: Text('Outlet Assets'),
              subtitle: Text('View deployed assets or deploy warehouse stock')),
          ListTile(
            leading: const Icon(Icons.inventory_2_outlined),
            title: const Text('Asset List'),
            onTap: () {
              Navigator.pop(sheetContext);
              context.push('/outlet/${widget.outletId}/assets');
            },
          ),
          ListTile(
            leading: const Icon(Icons.add_box_outlined),
            title: const Text('New Asset'),
            onTap: () {
              Navigator.pop(sheetContext);
              context.push('/outlet/${widget.outletId}/assets/new');
            },
          ),
        ]),
      ),
    );
  }

  Future<void> _checkIn() async {
    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) return;

    final purpose = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('Select Visit Purpose'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'order'),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child: Text('Order Collection', style: TextStyle(fontSize: 16)),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'payment'),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child: Text('Payment Collection', style: TextStyle(fontSize: 16)),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'follow_up'),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child:
                  Text('Follow-up / Feedback', style: TextStyle(fontSize: 16)),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'cold_call'),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child:
                  Text('Cold Call / Lead Gen', style: TextStyle(fontSize: 16)),
            ),
          ),
        ],
      ),
    );

    if (purpose == null) return;

    setState(() => _loading = true);
    try {
      final pos = await AttendanceService.getCurrentPosition();
      final service = ref.read(visitServiceProvider);
      final record = await service.checkIn(
        outletId: outlet.id,
        lat: pos.latitude,
        lng: pos.longitude,
        purpose: purpose,
      );

      final activeVisits = ref.read(activeVisitProvider);
      ref.read(activeVisitProvider.notifier).state = {
        ...activeVisits,
        outlet.id: record,
      };

      _startTimerIfNeeded();
      await ref.read(attendanceProvider.notifier).refresh();

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              'Checked In! Distance: ${record.distanceFromOutlet?.toStringAsFixed(0) ?? '?'} meters'),
          backgroundColor: Colors.green.shade700,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text('Check in failed: $e'),
            backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkOut(VisitRecord visit) async {
    setState(() => _loading = true);
    try {
      final service = ref.read(visitServiceProvider);
      final response = await service.checkOut(visit.id);

      final activeVisits = ref.read(activeVisitProvider);
      final newVisits = Map<int, VisitRecord>.from(activeVisits)
        ..remove(widget.outletId);
      ref.read(activeVisitProvider.notifier).state = newVisits;

      _timer?.cancel();
      _elapsed = Duration.zero;

      await ref.read(attendanceProvider.notifier).refresh();

      final flagged = response['flagged'] == true;
      final duration = response['duration_minutes'] ?? 0;

      if (!mounted) return;
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Visit Completed'),
          content: Text(
            flagged
                ? 'Visit checked out. Duration: $duration min.\n\n⚠️ Warning: This visit was flagged as too short (< 2 min) on the server.'
                : 'Visit logged successfully. Duration: $duration min.',
          ),
          actions: [
            TextButton(
              child: const Text('OK'),
              onPressed: () => Navigator.pop(ctx),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text('Check out failed: $e'),
            backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _completeNoOrder(VisitRecord visit) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('No Order Reason'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'Reason',
            hintText: 'Why was no order placed?',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) Navigator.pop(ctx, value);
            },
            child: const Text('Complete Visit'),
          ),
        ],
      ),
    );
    if (!mounted) {
      controller.dispose();
      return;
    }
    controller.dispose();
    if (reason == null) return;

    setState(() => _loading = true);
    try {
      final service = ref.read(visitServiceProvider);
      await service.checkOut(visit.id, noOrderReason: reason);
      final visits = Map<int, VisitRecord>.from(ref.read(activeVisitProvider))
        ..remove(widget.outletId);
      ref.read(activeVisitProvider.notifier).state = visits;
      _timer?.cancel();
      ref.read(attendanceProvider.notifier).refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Visit completed with No Order Reason.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Could not complete visit: $e'),
              backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final outlet = ref.watch(selectedOutletProvider);
    if (outlet == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Outlet Details')),
        body: const Center(child: Text('No outlet selected')),
      );
    }

    final activeVisits = ref.watch(activeVisitProvider);
    final visit = activeVisits[outlet.id];
    final isVisiting = visit != null;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(outlet.name),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (outlet.isIncomplete) ...[
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF2F2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFFFCA5A5)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Row(
                              children: [
                                Icon(Icons.warning_amber_rounded,
                                    color: Color(0xFFDC2626), size: 20),
                                SizedBox(width: 8),
                                Text(
                                  'Mandatory Check Failed',
                                  style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: Color(0xFFDC2626),
                                      fontSize: 14),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Missing: ${outlet.missingFields.join(', ')}. Please update outlet details below to trigger Edit Approval flow.',
                              style: const TextStyle(
                                  color: Color(0xFF7F1D1D), fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                    ],
                    Card(
                      elevation: 2,
                      shadowColor:
                          theme.colorScheme.shadow.withValues(alpha: 0.04),
                      child: Padding(
                        padding: const EdgeInsets.all(18.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Text(
                                    outlet.name,
                                    style: theme.textTheme.titleLarge?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 10, vertical: 6),
                                  decoration: BoxDecoration(
                                    color: theme.colorScheme.primary
                                        .withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    outlet.channelLabel,
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: theme.colorScheme.primary,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text('Code: ${outlet.code}',
                                style: theme.textTheme.bodyMedium),
                            const Divider(height: 24),
                            _buildInfoRow(context, Icons.person_outline_rounded,
                                'Owner', outlet.ownerName ?? 'Not Available'),
                            const SizedBox(height: 10),
                            _buildInfoRow(context, Icons.phone_android_rounded,
                                'Contact', outlet.mobile ?? 'Not Available'),
                            const SizedBox(height: 10),
                            _buildInfoRow(context, Icons.location_on_rounded,
                                'Address', outlet.address ?? 'Not Available'),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    if (isVisiting) ...[
                      Card(
                        elevation: 2,
                        shadowColor:
                            theme.colorScheme.shadow.withValues(alpha: 0.04),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                          side: BorderSide(
                              color: Colors.green.shade400, width: 1.0),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(18.0),
                          child: Column(
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      Icon(Icons.timer_outlined,
                                          color: Colors.green.shade600),
                                      const SizedBox(width: 8),
                                      Text(
                                        'Active Visit Timer',
                                        style: theme.textTheme.titleMedium
                                            ?.copyWith(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green.shade600,
                                        ),
                                      ),
                                    ],
                                  ),
                                  Text(
                                    '${_elapsed.inMinutes.toString().padLeft(2, '0')}:${(_elapsed.inSeconds % 60).toString().padLeft(2, '0')}',
                                    style: theme.textTheme.titleLarge?.copyWith(
                                      fontFamily: 'monospace',
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 20),
                              ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: theme.colorScheme.error,
                                ),
                                onPressed: () => _checkOut(visit),
                                child: const Text('End Visit (Check Out)'),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Outlet Activities',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                      const SizedBox(height: 12),
                      GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.3,
                        children: [
                          _buildActivityButton(
                            context,
                            title: 'New Order',
                            icon: Icons.add_shopping_cart_rounded,
                            color: theme.colorScheme.primary,
                            onTap: () => context.push('/order/new'),
                          ),
                          _buildActivityButton(
                            context,
                            title: 'No Order Reason',
                            icon: Icons.comments_disabled_rounded,
                            color: Colors.orange.shade700,
                            onTap: () => _completeNoOrder(visit),
                          ),
                          _buildActivityButton(
                            context,
                            title: 'New MR',
                            icon: Icons.assignment_rounded,
                            color: Colors.amber.shade700,
                            onTap: () => context.push(
                                '/outlet/${widget.outletId}/material-requests/new'),
                          ),
                          _buildActivityButton(
                            context,
                            title: 'Log Expense',
                            icon: Icons.receipt_long_rounded,
                            color: Colors.pink.shade600,
                            onTap: () => context.push('/expense'),
                          ),
                          _buildActivityButton(
                            context,
                            title: 'Assets',
                            icon: Icons.inventory_2_rounded,
                            color: Colors.indigo.shade600,
                            onTap: () => _showAssetActions(),
                          ),
                        ],
                      ),
                    ] else ...[
                      const SizedBox(height: 10),
                      ElevatedButton(
                        onPressed: _checkIn,
                        child: const Text('Check In to Outlet'),
                      ),
                    ]
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildInfoRow(
      BuildContext context, IconData icon, String label, String value) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: theme.textTheme.bodyMedium?.color, size: 18),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: theme.textTheme.bodyLarge?.copyWith(
              fontSize: 13,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActivityButton(
    BuildContext context, {
    required String title,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    return Card(
      elevation: 2,
      shadowColor: theme.colorScheme.shadow.withValues(alpha: 0.04),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 10),
              Text(
                title,
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
