import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../services/image_picker_service.dart';
import 'vendor_admin_screen.dart';
import 'procurement_map.dart';

class VendorTechScreen extends ConsumerStatefulWidget {
  const VendorTechScreen({super.key});
  @override
  ConsumerState<VendorTechScreen> createState() => _VendorTechScreenState();
}

class _VendorTechScreenState extends ConsumerState<VendorTechScreen> {
  int _tab = 0;
  bool _loading = true;
  bool _mapView = false;
  List<dynamic> _mrs = [], _items = [], _assets = [], _maintenance = [];
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final s = ref.read(procurementServiceProvider);
      final values = await Future.wait(
          [s.materialRequests(), s.items(), s.assets(), s.maintenanceLogs()]);
      if (mounted) {
        setState(() {
          _mrs = values[0];
          _items = values[1];
          _assets = values[2];
          _maintenance = values[3];
        });
      }
    } catch (e) {
      if (mounted) _message('Unable to load technician assignments: $e');
    }
    if (mounted) setState(() => _loading = false);
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  Future<List<String>?> _twoImages() async {
    final picker = ImagePickerService();
    final paths = <String>[];
    for (var i = 0; i < 2; i++) {
      final image = await picker.showImageSourceDialog(context);
      if (image == null) return null;
      paths.add(image.path);
    }
    final service = ref.read(procurementServiceProvider);
    return Future.wait(paths.map(service.uploadImage));
  }

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
              ],
            ));
  }

  Future<void> _recce(Map<String, dynamic> mr) async {
    final description =
        await _text('Submit Recce', 'Description and location constraints');
    if (description == null || description.isEmpty) return;
    final images = await _twoImages();
    if (images == null) return;
    try {
      await ref.read(procurementServiceProvider).submitRecce(mr['id'], {
        'description': description,
        'location_notes': description,
        'dimensions': mr['approx_dimensions'],
        'image_urls': images,
      });
      _message('Recce submitted for L3/L4 approval.');
      await _load();
    } catch (e) {
      _message('Recce submission failed: $e');
    }
  }

  Future<void> _deploy(Map<String, dynamic> item) async {
    final description = await _text(
        'Deploy Item ${item['batch_number']}', 'Installation description');
    if (description == null || description.isEmpty) return;
    if (!mounted) return;
    final image = await ImagePickerService().showImageSourceDialog(context);
    if (image == null) return;
    try {
      final url =
          await ref.read(procurementServiceProvider).uploadImage(image.path);
      await ref
          .read(procurementServiceProvider)
          .deployItem(item['id'], description, url);
      _message('Item installed and Asset created.');
      await _load();
    } catch (e) {
      _message('Installation failed: $e');
    }
  }

  Future<void> _createMaintenance(Map<String, dynamic> asset) async {
    final issue = await _text('Create Maintenance Log', 'Issue description');
    if (issue == null || issue.isEmpty) return;
    if (!mounted) return;
    final image = await ImagePickerService().showImageSourceDialog(context);
    if (!mounted) return;
    final urls = image == null
        ? <String>[]
        : [await ref.read(procurementServiceProvider).uploadImage(image.path)];
    try {
      await ref
          .read(procurementServiceProvider)
          .createMaintenance(asset['id'], issue, urls);
      await _load();
    } catch (e) {
      _message('Maintenance creation failed: $e');
    }
  }

  Future<void> _progress(Map<String, dynamic> log) async {
    final value =
        await _text('Report Maintenance Progress', 'Percentage 0–100');
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
          log['id'], int.parse(value), 'Technician update',
          imageUrls: urls);
      await _load();
    } catch (e) {
      _message('Progress failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Vendor Technician Portal'), actions: [
          if (_tab == 0 || _tab == 1)
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
                ButtonSegment(value: 0, label: Text('Recce')),
                ButtonSegment(value: 1, label: Text('Ready Items')),
                ButtonSegment(value: 2, label: Text('Assets')),
                ButtonSegment(value: 3, label: Text('Maintenance')),
              ], selected: {
                _tab
              }, onSelectionChanged: (v) => setState(() => _tab = v.first))),
          Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _mapView && (_tab == 0 || _tab == 1)
                      ? ProcurementMap(records: _tab == 0 ? _mrs : _items)
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView(
                              padding: const EdgeInsets.all(12),
                              children: _cards()))),
        ]),
      );
  List<Widget> _cards() {
    final records = [_mrs, _items, _assets, _maintenance][_tab];
    if (records.isEmpty) {
      return [
        const SizedBox(
            height: 300, child: Center(child: Text('No assigned records.')))
      ];
    }
    return records.map((raw) {
      final r = raw as Map<String, dynamic>;
      String title, subtitle, label;
      VoidCallback? action;
      if (_tab == 0) {
        title = r['mr_number'];
        subtitle = '${r['status']} • ${r['product_name'] ?? ''}';
        label = 'Submit Recce';
        if (r['status'] == 'vendor_assigned' ||
            r['status'] == 'recce_completed') {
          action = () => _recce(r);
        }
      } else if (_tab == 1) {
        title = r['batch_number'];
        subtitle = '${r['item_name']} • ${r['status']}';
        label = 'Deploy Item';
        if (r['status'] == 'Ready') action = () => _deploy(r);
      } else if (_tab == 2) {
        title = r['ac_number'];
        subtitle = '${r['asset_state']} • ${r['outlet_name'] ?? ''}';
        label = 'Maintenance';
        action = () => _createMaintenance(r);
      } else {
        title = 'Maintenance #${r['id']}';
        subtitle = '${r['status']} • ${r['progress_percent']}%';
        label = 'Report Progress';
        if (r['status'] != 'Validated') action = () => _progress(r);
      }
      return Card(
          child: ListTile(
              title: Text(title),
              subtitle: Text(subtitle),
              trailing: action == null
                  ? null
                  : TextButton(onPressed: action, child: Text(label))));
    }).toList();
  }
}
