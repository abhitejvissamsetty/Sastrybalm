import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';

class JointWorkingScreen extends ConsumerStatefulWidget {
  const JointWorkingScreen({super.key});

  @override
  ConsumerState<JointWorkingScreen> createState() => _JointWorkingScreenState();
}

class _JointWorkingScreenState extends ConsumerState<JointWorkingScreen> {
  int _step = 1;
  List<dynamic> _subordinates = [];
  Map<String, dynamic>? _selectedSubordinate;
  List<dynamic> _beats = [];
  Map<String, dynamic>? _selectedBeat;
  List<dynamic> _outlets = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _fetchSubordinates();
  }

  void _showToast(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          message,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: Colors.white),
        ),
        backgroundColor: isError ? const Color(0xFF09090B) : const Color(0xFF16A34A),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  Future<void> _fetchSubordinates() async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final response = await client.dio.get('/subordinates');
      if (mounted) {
        setState(() {
          _subordinates = response.data['items'] as List;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        _showToast('Unable to load subordinate users.', isError: true);
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _fetchBeats(int subUserId, String subUserName) async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final response = await client.dio.get('/subordinates/$subUserId/beats');
      final items = response.data['items'] as List;
      if (mounted) {
        if (items.isEmpty) {
          _showToast('No active beat plan assigned to $subUserName.', isError: true);
          setState(() => _loading = false);
        } else {
          setState(() {
            _beats = items;
            _step = 2;
            _loading = false;
          });
        }
      }
    } catch (_) {
      if (mounted) {
        _showToast('Unable to load beats for $subUserName.', isError: true);
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _fetchOutlets(int beatId) async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final response = await client.dio.get('/outlets', queryParameters: {'beat_id': beatId});
      if (mounted) {
        setState(() {
          _outlets = response.data['items'] as List;
          _step = 3;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        _showToast('Unable to load outlets for selected beat.', isError: true);
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _submitJointVisit(int outletId) async {
    final notesCtrl = TextEditingController();
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Log Joint Visit'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Log joint working visit notes with subordinate rep.'),
            const SizedBox(height: 12),
            TextField(
              controller: notesCtrl,
              decoration: const InputDecoration(labelText: 'Joint Visit Notes', hintText: 'e.g. Coached rep on outlet merchandising'),
            ),
          ],
        ),
        actions: [
          TextButton(child: const Text('Cancel'), onPressed: () => Navigator.pop(ctx, false)),
          ElevatedButton(child: const Text('Submit Visit'), onPressed: () => Navigator.pop(ctx, true)),
        ],
      ),
    );

    if (confirm == true) {
      try {
        final client = ref.read(apiClientProvider);
        await client.dio.post('/visits/joint', data: {
          'subordinate_user_id': _selectedSubordinate!['id'],
          'outlet_id': outletId,
          'notes': notesCtrl.text.trim(),
          'gps_lat': 12.9716,
          'gps_lng': 77.5946,
        });
        if (mounted) {
          _showToast('Joint Visit recorded successfully!');
        }
      } catch (_) {
        if (mounted) {
          _showToast('Failed to record joint visit.', isError: true);
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: Text(_step == 1 ? 'Select Subordinate User' : _step == 2 ? 'Select Beat' : 'Outlets (Joint Working)'),
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF09090B)))
          : Padding(
              padding: const EdgeInsets.all(20),
              child: _step == 1 ? _buildStep1() : _step == 2 ? _buildStep2() : _buildStep3(),
            ),
    );
  }

  Widget _buildStep1() {
    if (_subordinates.isEmpty) {
      return const Center(child: Text('No subordinate field reps found in hierarchy.'));
    }
    return ListView.separated(
      itemCount: _subordinates.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (ctx, i) {
        final user = _subordinates[i];
        return Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE4E4E7)),
          ),
          child: ListTile(
            leading: const CircleAvatar(backgroundColor: Color(0xFF09090B), child: Icon(Icons.person, color: Colors.white)),
            title: Text(user['full_name'], style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(user['role'].toString().toUpperCase()),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () {
              setState(() => _selectedSubordinate = user);
              _fetchBeats(user['id'], user['full_name']);
            },
          ),
        );
      },
    );
  }

  Widget _buildStep2() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Subordinate: ${_selectedSubordinate?['full_name']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 14),
        Expanded(
          child: ListView.separated(
            itemCount: _beats.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (ctx, i) {
              final beat = _beats[i];
              return Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE4E4E7)),
                ),
                child: ListTile(
                  leading: const Icon(Icons.map_rounded, color: Color(0xFF09090B)),
                  title: Text(beat['name'], style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text('Code: ${beat['code']}'),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () {
                    setState(() => _selectedBeat = beat);
                    _fetchOutlets(beat['id']);
                  },
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildStep3() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Beat: ${_selectedBeat?['name']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 14),
        Expanded(
          child: ListView.separated(
            itemCount: _outlets.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (ctx, i) {
              final o = _outlets[i];
              return Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE4E4E7)),
                ),
                child: ListTile(
                  leading: const Icon(Icons.storefront_rounded, color: Color(0xFF09090B)),
                  title: Text(o['name'], style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text(o['address'] ?? 'No address provided'),
                  trailing: ElevatedButton(
                    style: ElevatedButton.styleFrom(minimumSize: const Size(80, 36)),
                    child: const Text('Log Visit'),
                    onPressed: () => _submitJointVisit(o['id']),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
