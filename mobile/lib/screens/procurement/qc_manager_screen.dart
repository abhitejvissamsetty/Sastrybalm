import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../services/image_picker_service.dart';
import 'vendor_admin_screen.dart';

class QcManagerScreen extends ConsumerStatefulWidget {
  const QcManagerScreen({super.key});
  @override
  ConsumerState<QcManagerScreen> createState() => _QcManagerScreenState();
}

class _QcManagerScreenState extends ConsumerState<QcManagerScreen> {
  int _tab = 0;
  bool _loading = true;
  List<dynamic> _workOrders = [], _assets = [], _maintenanceLogs = [];
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final s = ref.read(procurementServiceProvider);
      final v =
          await Future.wait([s.workOrders(), s.assets(), s.maintenanceLogs()]);
      if (mounted) {
        setState(() {
          _workOrders = v[0];
          _assets = v[1];
          _maintenanceLogs = v[2];
        });
      }
    } catch (e) {
      if (mounted) _message('Unable to load QC records: $e');
    }
    if (mounted) setState(() => _loading = false);
  }

  void _message(String t) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t)));
  Future<String?> _text(String title, String label) {
    final c = TextEditingController();
    return showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
                title: Text(title),
                content: TextField(
                    controller: c,
                    maxLines: 3,
                    decoration: InputDecoration(labelText: label)),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel')),
                  ElevatedButton(
                      onPressed: () => Navigator.pop(ctx, c.text.trim()),
                      child: const Text('Continue'))
                ]));
  }

  Future<List<String>?> _images() async {
    final paths = <String>[];
    final picker = ImagePickerService();
    for (var i = 0; i < 2; i++) {
      final f = await picker.showImageSourceDialog(context);
      if (f == null) return null;
      paths.add(f.path);
    }
    return Future.wait(
        paths.map(ref.read(procurementServiceProvider).uploadImage));
  }

  Future<void> _completeQc(Map<String, dynamic> wo) async {
    final remark = await _text('QC Report', 'QC remark');
    if (remark == null || remark.isEmpty) return;
    final schedule = await _text(
            'Maintenance Schedule', 'Recommended maintenance schedule') ??
        '';
    final images = await _images();
    if (images == null) return;
    try {
      await ref.read(procurementServiceProvider).completeQc(wo['id'], {
        'final_dimensions': wo['recce']?['dimensions'] ?? 'Not specified',
        'final_specifications':
            wo['recce']?['material_specifications'] ?? 'As approved',
        'qc_notes': remark,
        'maintenance_schedule': schedule,
        'image_urls': images,
      });
      _message('QC completed and batch-controlled Item created.');
      await _load();
    } catch (e) {
      _message('QC completion failed: $e');
    }
  }

  Future<void> _returnProgress(Map<String, dynamic> wo) async {
    final value = await _text('Return Work Order', 'Progress below 100');
    if (value == null || int.tryParse(value) == null) return;
    final reason = await _text('QC Remark', 'Mandatory return reason');
    if (reason == null || reason.isEmpty) return;
    try {
      await ref
          .read(procurementServiceProvider)
          .reportWorkOrderProgress(wo['id'], int.parse(value), reason);
      await _load();
    } catch (e) {
      _message('QC return failed: $e');
    }
  }

  Future<void> _recall(Map<String, dynamic> wo) async {
    final reason = await _text('Recall for QC', 'Recall reason');
    if (reason == null || reason.isEmpty) return;
    try {
      await ref.read(procurementServiceProvider).recallQc(wo['id'], reason);
      await _load();
    } catch (e) {
      _message('Recall failed: $e');
    }
  }

  Future<void> _maintenance(Map<String, dynamic> asset) async {
    final issue = await _text('Create Maintenance Log', 'Issue description');
    if (issue == null || issue.isEmpty) return;
    try {
      await ref
          .read(procurementServiceProvider)
          .createMaintenance(asset['id'], issue, []);
      await _load();
    } catch (e) {
      _message('Maintenance creation failed: $e');
    }
  }

  Future<void> _validate(Map<String, dynamic> log) async {
    try {
      await ref.read(procurementServiceProvider).validateMaintenance(log['id']);
      await _load();
    } catch (e) {
      _message('Validation failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('QC Manager Portal')),
      body: Column(children: [
        SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(8),
            child: SegmentedButton<int>(segments: const [
              ButtonSegment(value: 0, label: Text('Work Orders')),
              ButtonSegment(value: 1, label: Text('Assets')),
              ButtonSegment(value: 2, label: Text('Maintenance'))
            ], selected: {
              _tab
            }, onSelectionChanged: (v) => setState(() => _tab = v.first))),
        Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                        padding: const EdgeInsets.all(12),
                        children: _cards()))),
      ]));
  List<Widget> _cards() {
    final records = [_workOrders, _assets, _maintenanceLogs][_tab];
    if (records.isEmpty) {
      return [
        const SizedBox(
            height: 300, child: Center(child: Text('No QC records.')))
      ];
    }
    return records.map((raw) {
      final r = raw as Map<String, dynamic>;
      String title, subtitle;
      List<Widget> actions = [];
      if (_tab == 0) {
        title = r['wo_number'];
        subtitle = '${r['status']} • ${r['progress_percent']}%';
        if (r['status'] == 'QC Pending') {
          actions = [
            TextButton(
                onPressed: () => _returnProgress(r),
                child: const Text('Return')),
            TextButton(
                onPressed: () => _completeQc(r), child: const Text('QC Report'))
          ];
        }
        if (r['status'] == 'Completed') {
          actions = [
            TextButton(
                onPressed: () => _recall(r), child: const Text('Recall QC'))
          ];
        }
      } else if (_tab == 1) {
        title = r['ac_number'];
        subtitle = '${r['asset_state']} • ${r['outlet_name'] ?? ''}';
        actions = [
          TextButton(
              onPressed: () => _maintenance(r),
              child: const Text('Maintenance'))
        ];
      } else {
        title = 'Maintenance #${r['id']}';
        subtitle = '${r['status']} • ${r['progress_percent']}%';
        if (r['status'] == 'Completed') {
          actions = [
            TextButton(
                onPressed: () => _validate(r), child: const Text('Validate'))
          ];
        }
      }
      return Card(
          child: ListTile(
              title: Text(title),
              subtitle: Text(subtitle),
              trailing:
                  Row(mainAxisSize: MainAxisSize.min, children: actions)));
    }).toList();
  }
}
