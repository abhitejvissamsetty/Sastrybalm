import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';

class QcManagerScreen extends ConsumerStatefulWidget {
  const QcManagerScreen({super.key});

  @override
  ConsumerState<QcManagerScreen> createState() => _QcManagerScreenState();
}

class _QcManagerScreenState extends ConsumerState<QcManagerScreen> {
  int _selectedTab = 0;
  bool _loading = false;
  List<dynamic> _vendors = [];
  List<dynamic> _workOrders = [];
  List<dynamic> _assets = [];

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final vendorsRes = await client.dio.get('/procurement/vendors');
      final woRes = await client.dio.get('/procurement/work-orders');
      final itemsRes = await client.dio.get('/procurement/items');

      if (mounted) {
        setState(() {
          _vendors = vendorsRes.data['items'] as List;
          _workOrders = woRes.data['items'] as List;
          _assets = itemsRes.data['items'] as List;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _processQcInspection(Map<String, dynamic> wo) async {
    final dimsCtrl = TextEditingController(text: wo['recce']?['dimensions'] ?? '10ft x 4ft');
    final specsCtrl = TextEditingController(text: wo['recce']?['material_specifications'] ?? 'Acrylic 3mm LED');
    final notesCtrl = TextEditingController();
    final batchCtrl = TextEditingController(text: 'BATCH-${DateTime.now().millisecondsSinceEpoch.toString().substring(5)}');

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('QC Verification & Batch Allocation'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Work Order: ${wo['wo_number']}', style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(controller: dimsCtrl, decoration: const InputDecoration(labelText: 'Final Verified Dimensions')),
              const SizedBox(height: 10),
              TextField(controller: specsCtrl, decoration: const InputDecoration(labelText: 'Final Material Specifications')),
              const SizedBox(height: 10),
              TextField(controller: batchCtrl, decoration: const InputDecoration(labelText: 'Batch Number Allocation')),
              const SizedBox(height: 10),
              TextField(controller: notesCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'QC Review Notes & Comments')),
            ],
          ),
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Approve & Convert to Item'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/work-orders/${wo['id']}/qc-complete', data: {
          'final_dimensions': dimsCtrl.text.trim(),
          'final_specifications': specsCtrl.text.trim(),
          'qc_notes': notesCtrl.text.trim(),
          'batch_number': batchCtrl.text.trim(),
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Work Order verified & Item Batch created!')),
          );
          _fetchData();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('QC Inspection error: $e')));
        }
      }
    }
  }

  Future<void> _addMaintenanceLog(int assetId) async {
    final notesCtrl = TextEditingController();
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Asset Maintenance Log'),
        content: TextField(
          controller: notesCtrl,
          maxLines: 3,
          decoration: const InputDecoration(labelText: 'Maintenance Notes & Inspection Summary'),
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Submit Log'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true && notesCtrl.text.trim().isNotEmpty) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/assets/$assetId/maintenance-logs', data: {
          'notes': notesCtrl.text.trim(),
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Maintenance log submitted!')),
          );
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('QC Manager Portal'),
        elevation: 0,
      ),
      body: Column(
        children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _buildTabPill(0, 'Vendors & Work Orders'),
                const SizedBox(width: 8),
                _buildTabPill(1, 'Assets & Maintenance'),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF09090B)))
                : Padding(
                    padding: const EdgeInsets.all(16),
                    child: _selectedTab == 0 ? _buildWorkOrdersTab() : _buildAssetsTab(),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabPill(int index, String label) {
    final selected = _selectedTab == index;
    return GestureDetector(
      onTap: () => setState(() => _selectedTab = index),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF09090B) : const Color(0xFFF4F4F5),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : const Color(0xFF09090B),
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
        ),
      ),
    );
  }

  Widget _buildWorkOrdersTab() {
    if (_workOrders.isEmpty) {
      return const Center(child: Text('No pending Work Orders for QC inspection.'));
    }
    return ListView.separated(
      itemCount: _workOrders.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (ctx, i) {
        final wo = _workOrders[i];
        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE4E4E7)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(wo['wo_number'] ?? 'WO-${wo['id']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: const Color(0xFFF4F4F5), borderRadius: BorderRadius.circular(8)),
                    child: Text(wo['status'].toString().toUpperCase(), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text('Outlet: ${wo['outlet']?['name'] ?? 'Assigned Store'}', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF09090B)),
                  onPressed: () => _processQcInspection(wo),
                  child: const Text('Perform QC Inspection & Allocate Batch ID'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildAssetsTab() {
    if (_assets.isEmpty) {
      return const Center(child: Text('No Assets available.'));
    }
    return ListView.separated(
      itemCount: _assets.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (ctx, i) {
        final asset = _assets[i];
        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE4E4E7)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(asset['item_name'] ?? 'Asset Item', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 4),
              Text('Batch Code: ${asset['item_code'] ?? 'N/A'}', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 10),
              ElevatedButton.icon(
                icon: const Icon(Icons.build_outlined, size: 16),
                label: const Text('Create Maintenance Log'),
                onPressed: () => _addMaintenanceLog(asset['id']),
              ),
            ],
          ),
        );
      },
    );
  }
}
