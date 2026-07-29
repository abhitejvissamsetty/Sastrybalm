import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/auth_provider.dart';
import '../../services/image_picker_service.dart';
import '../../services/operations_service.dart';

final mrServiceProvider =
    Provider((ref) => MaterialRequestService(ref.watch(apiClientProvider)));

class MrScreen extends ConsumerStatefulWidget {
  final int outletId;
  const MrScreen({super.key, required this.outletId});
  @override
  ConsumerState<MrScreen> createState() => _MrScreenState();
}

class _MrScreenState extends ConsumerState<MrScreen> {
  final _description = TextEditingController();
  final _dimensions = List.generate(4, (_) => TextEditingController());
  final _picker = ImagePickerService();
  Map<String, dynamic>? _context;
  int? _productId;
  final List<XFile?> _images = [null, null, null];
  bool _loading = true, _submitting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      _context = await ref.read(mrServiceProvider).getContext(widget.outletId);
    } catch (e) {
      if (mounted) _message('Unable to load request form: $e');
    }
    if (mounted) setState(() => _loading = false);
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  double? _number(int index) => double.tryParse(_dimensions[index].text.trim());

  Future<void> _pick(int index) async {
    final image = await _picker.showImageSourceDialog(context);
    if (image != null && mounted) setState(() => _images[index] = image);
  }

  Future<void> _submit() async {
    if (_productId == null ||
        _description.text.trim().length < 5 ||
        _images.any((e) => e == null)) {
      _message(
          'Select one product, enter a clear description, and attach all three images.');
      return;
    }
    if (_dimensions
        .any((c) => c.text.isNotEmpty && (double.tryParse(c.text) ?? 0) <= 0)) {
      _message('Dimensions must be positive numbers.');
      return;
    }
    setState(() => _submitting = true);
    try {
      final result = await ref.read(mrServiceProvider).submitRequest(
            outletId: widget.outletId,
            productId: _productId!,
            description: _description.text.trim(),
            length: _number(0),
            width: _number(1),
            height: _number(2),
            depth: _number(3),
            presentOutletImagePath: _images[0]!.path,
            installationPlaceImagePath: _images[1]!.path,
            customerApprovalLetterImagePath: _images[2]!.path,
          );
      if (mounted) {
        _message('Material Request ${result['mr_number']} submitted.');
        context.pop();
      }
    } catch (e) {
      if (mounted) _message('Submission failed: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final outlet = _context?['outlet'] as Map<String, dynamic>?;
    final products = (_context?['products'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('New Material Request')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(outlet?['name'] ?? 'Outlet',
                            style: Theme.of(context).textTheme.titleMedium),
                        Text(outlet?['address'] ?? 'Address unavailable'),
                        Text(outlet?['contact'] ?? 'Contact unavailable'),
                        Text(
                            'Location: ${outlet?['gps_lat'] ?? '—'}, ${outlet?['gps_lng'] ?? '—'}'),
                      ]))),
          const SizedBox(height: 16),
          DropdownButtonFormField<int>(
            initialValue: _productId,
            decoration:
                const InputDecoration(labelText: 'Procurement Product *'),
            items: products
                .map<DropdownMenuItem<int>>((p) => DropdownMenuItem(
                      value: p['id'] as int,
                      child: Text('${p['name']} (${p['sku'] ?? 'No SKU'})'),
                    ))
                .toList(),
            onChanged: (v) => setState(() => _productId = v),
          ),
          const SizedBox(height: 16),
          TextField(
              controller: _description,
              maxLines: 4,
              maxLength: 2000,
              decoration:
                  const InputDecoration(labelText: 'Request Description *')),
          const SizedBox(height: 8),
          const Text('Dimensions (optional)'),
          Row(
              children: List.generate(
                  4,
                  (i) => Expanded(
                          child: Padding(
                        padding: EdgeInsets.only(right: i == 3 ? 0 : 8),
                        child: TextField(
                            controller: _dimensions[i],
                            keyboardType: const TextInputType.numberWithOptions(
                                decimal: true),
                            decoration: InputDecoration(
                                labelText: [
                              'Length',
                              'Width',
                              'Height',
                              'Depth'
                            ][i])),
                      )))),
          const SizedBox(height: 16),
          ...List.generate(
              3,
              (i) => _ImageField(
                    label: [
                      'Present Outlet Image *',
                      'Installation Place Image *',
                      'Customer Approval Letter Image *'
                    ][i],
                    image: _images[i],
                    onTap: () => _pick(i),
                  )),
          const SizedBox(height: 12),
          ElevatedButton(
              onPressed: _submitting ? null : _submit,
              child: Text(
                  _submitting ? 'Submitting…' : 'Submit Material Request')),
        ]),
      ),
    );
  }
}

class _ImageField extends StatelessWidget {
  final String label;
  final XFile? image;
  final VoidCallback onTap;
  const _ImageField(
      {required this.label, required this.image, required this.onTap});
  @override
  Widget build(BuildContext context) => Card(
          child: ListTile(
        leading: image == null
            ? const Icon(Icons.add_a_photo_outlined)
            : ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.file(File(image!.path),
                    width: 54, height: 54, fit: BoxFit.cover)),
        title: Text(label),
        subtitle: Text(image == null ? 'Camera or gallery' : 'Tap to replace'),
        onTap: onTap,
      ));
}
