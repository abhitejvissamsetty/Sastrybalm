import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/beat_provider.dart';
import '../../services/operations_service.dart';

final mrServiceProvider = Provider((ref) {
  final client = ref.watch(apiClientProvider);
  return MaterialRequestService(client);
});

class MrScreen extends ConsumerStatefulWidget {
  const MrScreen({super.key});

  @override
  ConsumerState<MrScreen> createState() => _MrScreenState();
}

class _MrScreenState extends ConsumerState<MrScreen> {
  final _descCtrl = TextEditingController();
  final _categoryCtrl = TextEditingController();
  bool _submitting = false;

  Future<void> _submitRequest() async {
    final desc = _descCtrl.text.trim();
    if (desc.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a description for the material request')),
      );
      return;
    }

    final outlet = ref.read(selectedOutletProvider);
    if (outlet == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an outlet from the beat plan first')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      final service = ref.read(mrServiceProvider);
      final response = await service.submitRequest(
        outletId: outlet.id,
        description: desc,
        category: _categoryCtrl.text.trim().isNotEmpty ? _categoryCtrl.text.trim() : null,
      );

      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Request Submitted'),
            content: Text(
              'Material request submitted to CMMS.\n\nMR Code: ${response['mr_number'] ?? '#${response['id']}'}\nStatus: ${response['status'] ?? 'submitted'}',
            ),
            actions: [
              TextButton(
                child: const Text('OK'),
                onPressed: () {
                  Navigator.pop(ctx);
                  context.pop();
                },
              ),
            ],
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to submit material request: $e'), backgroundColor: Colors.red.shade700),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final outlet = ref.watch(selectedOutletProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('CMMS Material Request'),
      ),
      body: _submitting
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (outlet != null) ...[
                      Card(
                        elevation: 2,
                        shadowColor: theme.colorScheme.shadow.withOpacity(0.04),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Requesting For Outlet', style: theme.textTheme.bodyMedium),
                              const SizedBox(height: 6),
                              Text(
                                outlet.name,
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(outlet.code, style: theme.textTheme.bodyMedium),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],
                    TextField(
                      controller: _categoryCtrl,
                      decoration: const InputDecoration(
                        labelText: 'CMMS Item Code / Category (Optional)',
                        hintText: 'e.g. DISPLAY_STAND_LARGE',
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _descCtrl,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Requested Materials & Description',
                        hintText: 'e.g. Requesting countertop display stand.',
                      ),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _submitRequest,
                      child: const Text('Submit Material Request'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
