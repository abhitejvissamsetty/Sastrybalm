import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';

class VendorTechScreen extends ConsumerStatefulWidget {
  const VendorTechScreen({super.key});

  @override
  ConsumerState<VendorTechScreen> createState() => _VendorTechScreenState();
}

class _VendorTechScreenState extends ConsumerState<VendorTechScreen> {
  int _selectedTab = 0;
  bool _loading = false;
  List<dynamic> _materialRequests = [];
  List<dynamic> _items = [];

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
      final itemsRes = await client.dio.get('/procurement/items');
      if (mounted) {
        setState(() {
          _materialRequests = mrRes.data['items'] as List;
          _items = itemsRes.data['items'] as List;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submitRecce(Map<String, dynamic> mr) async {
    final dimsCtrl = TextEditingController(text: mr['approx_dimensions'] ?? '10ft x 4ft');
    final specsCtrl = TextEditingController(text: mr['material_specifications'] ?? 'Standard Specs');
    final notesCtrl = TextEditingController();
    final photoCtrl = TextEditingController(text: 'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158');

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Submit On-Site Recce Information'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: dimsCtrl, decoration: const InputDecoration(labelText: 'Measured Dimensions')),
              const SizedBox(height: 10),
              TextField(controller: specsCtrl, decoration: const InputDecoration(labelText: 'Material Specifications')),
              const SizedBox(height: 10),
              TextField(controller: photoCtrl, decoration: const InputDecoration(labelText: 'Site Recce Photo URL')),
              const SizedBox(height: 10),
              TextField(controller: notesCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'Site Notes & Constraints')),
            ],
          ),
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Submit Recce'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/material-requests/${mr['id']}/recce', data: {
          'dimensions': dimsCtrl.text.trim(),
          'material_specifications': specsCtrl.text.trim(),
          'client_notes': notesCtrl.text.trim(),
          'photo_url': photoCtrl.text.trim(),
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Recce Information submitted!')));
          _fetchData();
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _createAssetFromItem(Map<String, dynamic> item) async {
    final photoCtrl = TextEditingController(text: 'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158');
    final notesCtrl = TextEditingController(text: 'Asset installed successfully at outlet.');

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Asset (Installation)'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Item Batch: ${item['batch_number']}', style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(controller: photoCtrl, decoration: const InputDecoration(labelText: 'Installation Asset Photo URL')),
            const SizedBox(height: 10),
            TextField(controller: notesCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'Installation Notes')),
          ],
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Create Asset'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/procurement/items/${item['id']}/create-asset', data: {
          'image_url': photoCtrl.text.trim(),
          'notes': notesCtrl.text.trim(),
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Asset installed and created successfully!')));
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
      appBar: AppBar(title: const Text('Vendor Technician Portal'), elevation: 0),
      body: Column(
        children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _buildTabPill(0, 'Recce Assignments'),
                const SizedBox(width: 8),
                _buildTabPill(1, 'Pending Asset Installations'),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF09090B)))
                : Padding(
                    padding: const EdgeInsets.all(16),
                    child: _selectedTab == 0 ? _buildRecceTab() : _buildItemsTab(),
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

  Widget _buildRecceTab() {
    if (_materialRequests.isEmpty) return const Center(child: Text('No assigned Recce tasks.'));
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
                onPressed: () => _submitRecce(mr),
                child: const Text('Submit On-Site Recce Info'),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildItemsTab() {
    if (_items.isEmpty) return const Center(child: Text('No pending Items for installation.'));
    return ListView.separated(
      itemCount: _items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (ctx, i) {
        final item = _items[i];
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
              Text(item['item_name'] ?? 'Item', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 4),
              Text('Batch Code: ${item['batch_number']}', style: const TextStyle(color: Color(0xFF71717A), fontSize: 12)),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: () => _createAssetFromItem(item),
                child: const Text('Create Asset & Complete Installation'),
              ),
            ],
          ),
        );
      },
    );
  }
}
