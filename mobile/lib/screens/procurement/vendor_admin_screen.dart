import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';
import '../../services/image_picker_service.dart';
import '../../services/procurement_service.dart';
import 'procurement_map.dart';

final procurementServiceProvider =
    Provider((ref) => ProcurementService(ref.watch(apiClientProvider)));

class VendorAdminScreen extends ConsumerStatefulWidget {
  const VendorAdminScreen({super.key});
  @override
  ConsumerState<VendorAdminScreen> createState() => _VendorAdminScreenState();
}

class _VendorAdminScreenState extends ConsumerState<VendorAdminScreen> {
  int _tab = 0;
  bool _loading = true;
  bool _mapView = false;
  List<dynamic> _mrs = [], _workOrders = [], _assets = [], _maintenance = [];
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final service = ref.read(procurementServiceProvider);
      final values = await Future.wait([
        service.materialRequests(),
        service.workOrders(),
        service.assets(),
        service.maintenanceLogs(),
      ]);
      if (mounted) {
        setState(() {
          _mrs = values[0];
          _workOrders = values[1];
          _assets = values[2];
          _maintenance = values[3];
        });
      }
    } catch (e) {
      if (mounted) _message('Unable to load Vendor records: $e');
    }
    if (mounted) setState(() => _loading = false);
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  Future<String?> _prompt(String title, String label,
      {String initial = ''}) async {
    final controller = TextEditingController(text: initial);
    return showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
              title: Text(title),
              content: TextField(
                  controller: controller,
                  maxLines: 3,
                  decoration: InputDecoration(labelText: label)),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Cancel')),
                ElevatedButton(
                    onPressed: () => Navigator.pop(ctx, controller.text.trim()),
                    child: const Text('Submit'))
              ],
            ));
  }

  Future<void> _quotation(Map<String, dynamic> mr) async {
    final base = await _prompt('Supplier Quotation', 'Non-GST Base Amount');
    if (base == null || double.tryParse(base) == null) return;
    final notes =
        await _prompt('Quotation Notes', 'Terms, lead time, and notes') ?? '';
    try {
      await ref.read(procurementServiceProvider).submitQuotation({
        'material_request_id': mr['id'],
        'base_amount': double.parse(base),
        'lead_time_days': 7,
        'notes': notes,
      });
      _message('Quotation submitted for manager approval.');
      await _load();
    } catch (e) {
      _message('Quotation failed: $e');
    }
  }

  Future<void> _woAction(Map<String, dynamic> wo) async {
    final status = wo['status'];
    try {
      if (status == 'Assigned' || status == 'Issued') {
        await ref.read(procurementServiceProvider).acknowledge(wo['id']);
      } else if (status == 'Acknowledged' || status == 'In Manufacturing') {
        final value = await _prompt(
            'Report Work Order Progress', 'Progress percentage',
            initial: '${wo['progress_percent'] ?? 0}');
        if (value == null || int.tryParse(value) == null) return;
        await ref.read(procurementServiceProvider).reportWorkOrderProgress(
            wo['id'], int.parse(value), 'Vendor progress update');
      } else {
        return;
      }
      await _load();
    } catch (e) {
      _message('Work Order update failed: $e');
    }
  }

  Future<void> _maintenanceProgress(Map<String, dynamic> log) async {
    final value = await _prompt('Maintenance Progress', 'Progress percentage',
        initial: '${log['progress_percent'] ?? 0}');
    if (value == null || int.tryParse(value) == null) return;
    if (!mounted) return;
    try {
      final image = await ImagePickerService().showImageSourceDialog(context);
      if (!mounted) return;
      final urls = image == null
          ? <String>[]
          : [
              await ref.read(procurementServiceProvider).uploadImage(image.path)
            ];
      await ref.read(procurementServiceProvider).reportMaintenance(
          log['id'], int.parse(value), 'Vendor maintenance update',
          imageUrls: urls);
      await _load();
    } catch (e) {
      _message('Progress update failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Vendor Admin Portal'), actions: [
          if (_tab == 0)
            IconButton(
              onPressed: () => setState(() => _mapView = !_mapView),
              icon: Icon(_mapView ? Icons.view_list : Icons.map_outlined),
            ),
        ]),
        body: Column(children: [
          SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.all(8),
              child: SegmentedButton<int>(segments: const [
                ButtonSegment(value: 0, label: Text('MRs')),
                ButtonSegment(value: 1, label: Text('Work Orders')),
                ButtonSegment(value: 2, label: Text('Assets')),
                ButtonSegment(value: 3, label: Text('Maintenance')),
              ], selected: {
                _tab
              }, onSelectionChanged: (v) => setState(() => _tab = v.first))),
          Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _mapView && _tab == 0
                      ? ProcurementMap(records: _mrs)
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView(
                              padding: const EdgeInsets.all(12),
                              children: _cards()),
                        )),
        ]),
      );
  List<Widget> _cards() {
    final records = [_mrs, _workOrders, _assets, _maintenance][_tab];
    if (records.isEmpty) {
      return [
        const SizedBox(
            height: 300,
            child: Center(child: Text('No records in this stage.')))
      ];
    }
    return records.map((raw) {
      final r = raw as Map<String, dynamic>;
      final title = _tab == 0
          ? r['mr_number']
          : _tab == 1
              ? r['wo_number']
              : _tab == 2
                  ? r['ac_number']
                  : 'Maintenance #${r['id']}';
      final subtitle = _tab == 0
          ? '${r['status']} • ${r['product_name'] ?? ''}'
          : _tab == 1
              ? '${r['status']} • ${r['progress_percent']}%'
              : _tab == 2
                  ? '${r['asset_state']} • ${r['outlet_name'] ?? ''}'
                  : '${r['status']} • ${r['progress_percent']}%';
      VoidCallback? action;
      String? label;
      if (_tab == 0 && r['recce']?['status'] == 'Approved') {
        action = () => _quotation(r);
        label = 'Submit Quotation';
      }
      if (_tab == 1 &&
          ['Assigned', 'Issued', 'Acknowledged', 'In Manufacturing']
              .contains(r['status'])) {
        action = () => _woAction(r);
        label = ['Assigned', 'Issued'].contains(r['status'])
            ? 'Acknowledge'
            : 'Report Progress';
      }
      if (_tab == 3 && r['status'] != 'Validated') {
        action = () => _maintenanceProgress(r);
        label = 'Report Progress';
      }
      return Card(
          child: ListTile(
              title: Text('$title'),
              subtitle: Text(subtitle),
              trailing: action == null
                  ? null
                  : TextButton(onPressed: action, child: Text(label!))));
    }).toList();
  }
}
