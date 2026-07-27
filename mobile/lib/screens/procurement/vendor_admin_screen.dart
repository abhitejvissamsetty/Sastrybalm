import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';

class VendorAdminScreen extends ConsumerStatefulWidget {
  const VendorAdminScreen({super.key});

  @override
  ConsumerState<VendorAdminScreen> createState() => _VendorAdminScreenState();
}

class _VendorAdminScreenState extends ConsumerState<VendorAdminScreen> {
  int _selectedTab = 0;
  bool _loading = false;
  List<dynamic> _materialRequests = [];
  List<dynamic> _workOrders = [];

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final mrRes = await client.dio.get('/material-requests');
      final woRes = await client.dio.get('/procurement/work-orders');
      if (mounted) {
        setState(() {
          _materialRequests = mrRes.data['items'] as List;
          _workOrders = woRes.data['items'] as List;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submitQuotation(Map<String, dynamic> mr) async {
    final amountCtrl = TextEditingController();
    final leadTimeCtrl = TextEditingController(text: '7');
    final recceNotesCtrl = TextEditingController(text: 'Counter-recce specs confirmed on site.');
    final notesCtrl = TextEditingController();

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Supplier Quotation'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Original MR Specs: ${mr['material_specifications'] ?? 'Standard'}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
              const SizedBox(height: 4),
              Text('Approx Dims: ${mr['approx_dimensions'] ?? 'N/A'}', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 12),
              TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Quotation Amount (INR)')),
              const SizedBox(height: 10),
              TextField(controller: leadTimeCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Lead Time (Days)')),
              const SizedBox(height: 10),
              TextField(controller: recceNotesCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'Counter-Recce Comparison Notes')),
              const SizedBox(height: 10),
              TextField(controller: notesCtrl, decoration: const InputDecoration(labelText: 'General Terms & Notes')),
            ],
          ),
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Submit Quotation'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true && amountCtrl.text.trim().isNotEmpty) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/quotations', data: {
          'material_request_id': mr['id'],
          'quote_amount': double.parse(amountCtrl.text.trim()),
          'lead_time_days': int.parse(leadTimeCtrl.text.trim()),
          'counter_recce_notes': recceNotesCtrl.text.trim(),
          'notes': notesCtrl.text.trim(),
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Supplier Quotation submitted successfully!')));
          _fetchData();
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _submitWoQc(Map<String, dynamic> wo) async {
    final photoCtrl = TextEditingController(text: 'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158');
    final notesCtrl = TextEditingController();

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Submit Work Order for QC Inspection'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: photoCtrl, decoration: const InputDecoration(labelText: 'Manufactured Product Photo URL')),
            const SizedBox(height: 10),
            TextField(controller: notesCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'Manufacturing Completion Notes')),
          ],
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Submit to QC Pending'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/work-orders/${wo['id']}/submit-qc', data: {
          'manufactured_photo_url': photoCtrl.text.trim(),
          'notes': notesCtrl.text.trim(),
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Work Order status updated to QC Pending!')));
          _fetchData();
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
      appBar: AppBar(title: const Text('Vendor Admin Portal'), elevation: 0),
      body: Column(
        children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _buildTabPill(0, 'Material Requests'),
                const SizedBox(width: 8),
                _buildTabPill(1, 'Work Orders'),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF09090B)))
                : Padding(
                    padding: const EdgeInsets.all(16),
                    child: _selectedTab == 0 ? _buildMrTab() : _buildWoTab(),
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

  Widget _buildMrTab() {
    if (_materialRequests.isEmpty) return const Center(child: Text('No assigned Material Requests.'));
    return ListView.separated(
      itemCount: _materialRequests.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (ctx, i) {
        final mr = _materialRequests[i];
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
              Text(mr['mr_number'] ?? 'MR-${mr['id']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 4),
              Text(mr['description'] ?? 'No description', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: () => _submitQuotation(mr),
                child: const Text('Create Supplier Quotation'),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildWoTab() {
    if (_workOrders.isEmpty) return const Center(child: Text('No active Work Orders.'));
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
              Text(wo['wo_number'] ?? 'WO-${wo['id']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 4),
              Text('Status: ${wo['status']}', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: () => _submitWoQc(wo),
                child: const Text('Mark Manufacturing Done & Submit to QC'),
              ),
            ],
          ),
        );
      },
    );
  }
}
