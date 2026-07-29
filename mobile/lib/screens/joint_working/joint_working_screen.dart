import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/auth_provider.dart';
import '../../services/attendance_service.dart';
import '../../services/image_picker_service.dart';

class JointWorkingScreen extends ConsumerStatefulWidget {
  const JointWorkingScreen({super.key});

  @override
  ConsumerState<JointWorkingScreen> createState() => _JointWorkingScreenState();
}

class _JointWorkingScreenState extends ConsumerState<JointWorkingScreen> {
  int _step = 1; // 1: Select Subordinate, 2: Select Beat, 3: Outlets
  int _viewMode = 0; // 0: List View, 1: Map View
  bool _showSearch = false;
  final TextEditingController _searchCtrl = TextEditingController();
  String _outletQuery = '';
  String _positionQuery = '';

  List<dynamic> _subordinates = [];
  Map<String, dynamic>? _selectedSubordinate;
  List<dynamic> _beats = [];
  Map<String, dynamic>? _selectedBeat;
  List<dynamic> _outlets = [];
  Map<String, dynamic>? _selectedMapOutlet;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _fetchSubordinates();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  void _showToast(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          message,
          style: const TextStyle(
              fontWeight: FontWeight.w600, fontSize: 13, color: Colors.white),
        ),
        backgroundColor:
            isError ? const Color(0xFF09090B) : const Color(0xFF16A34A),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  Future<void> _openGoogleMaps(double lat, double lng, String title) async {
    final url =
        Uri.parse('https://www.google.com/maps/search/?api=1&query=$lat,$lng');
    try {
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      } else {
        _showToast('Opening Google Maps location...', isError: false);
      }
    } catch (_) {
      _showToast('Redirecting to Google Maps ($lat, $lng)', isError: false);
    }
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
          _showToast('No active beat plan assigned to $subUserName.',
              isError: true);
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
      final response = await client.dio
          .get('/outlets', queryParameters: {'beat_id': beatId});
      if (mounted) {
        setState(() {
          _outlets = response.data['items'] as List;
          if (_outlets.isNotEmpty) {
            _selectedMapOutlet = _outlets.first as Map<String, dynamic>;
          }
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
    final noOrderReasonCtrl = TextEditingController();
    List<dynamic> l1OrdersToday = [];
    int? selectedOrderId;
    XFile? evidenceImage;
    bool loadingOrders = false;

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (modalCtx, modalSetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 20,
                bottom: MediaQuery.of(modalCtx).viewInsets.bottom + 20,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Joint Visit Outcomes',
                            style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: Color(0xFF09090B))),
                        IconButton(
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () => Navigator.pop(modalCtx),
                        ),
                      ],
                    ),
                    const Divider(),
                    const SizedBox(height: 8),

                    // Section 1: Notes / No Order Reason
                    const Text('1. Visit Notes & No Order Reason',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 8),
                    TextField(
                      controller: notesCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Joint Visit Notes',
                        hintText: 'e.g. Coached rep on outlet merchandising',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: noOrderReasonCtrl,
                      decoration: const InputDecoration(
                        labelText: 'No Order Reason (Optional)',
                        hintText: 'e.g. Sufficient stock available',
                        border: OutlineInputBorder(),
                      ),
                    ),

                    const SizedBox(height: 20),
                    // Section 2: Order Link & Fetch Today's Orders
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('2. Link Today\'s L1 Punched Order',
                            style: TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 14)),
                        ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF09090B)),
                          icon: loadingOrders
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2, color: Colors.white))
                              : const Icon(Icons.sync_rounded,
                                  size: 16, color: Colors.white),
                          label: const Text('Fetch Orders Today',
                              style:
                                  TextStyle(fontSize: 12, color: Colors.white)),
                          onPressed: loadingOrders
                              ? null
                              : () async {
                                  modalSetState(() => loadingOrders = true);
                                  try {
                                    final client = ref.read(apiClientProvider);
                                    final response = await client.dio.get(
                                        '/orders/outlet-today-l1-orders',
                                        queryParameters: {
                                          'outlet_id': outletId,
                                          if (_selectedBeat != null)
                                            'beat_id': _selectedBeat!['id'],
                                          if (_selectedSubordinate != null)
                                            'subordinate_user_id':
                                                _selectedSubordinate!['id'],
                                        });
                                    final fetched =
                                        response.data['orders'] as List;
                                    modalSetState(() {
                                      l1OrdersToday = fetched;
                                      loadingOrders = false;
                                    });
                                    if (fetched.isEmpty) {
                                      _showToast(
                                          'No orders punched for this outlet today by L1 users.');
                                    }
                                  } catch (err) {
                                    modalSetState(() => loadingOrders = false);
                                    _showToast(
                                        'Failed to fetch today\'s orders: $err',
                                        isError: true);
                                  }
                                },
                        ),
                      ],
                    ),
                    if (l1OrdersToday.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      DropdownButtonFormField<int>(
                        initialValue: selectedOrderId,
                        hint: const Text('Select Order ID Punched Today'),
                        items: l1OrdersToday.map<DropdownMenuItem<int>>((o) {
                          return DropdownMenuItem<int>(
                            value: o['id'] as int,
                            child: Text(
                                'Order ${o['order_number']} by ${o['user_name']} (₹${o['total_amount']})'),
                          );
                        }).toList(),
                        onChanged: (val) =>
                            modalSetState(() => selectedOrderId = val),
                        decoration:
                            const InputDecoration(border: OutlineInputBorder()),
                      ),
                    ],

                    const SizedBox(height: 20),
                    // Section 3: Image Evidence
                    const Text('3. Upload Store Photo Evidence',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.camera_alt_rounded),
                      label: Text(evidenceImage == null
                          ? 'Capture or Select Store Photo'
                          : 'Photo Ready: ${evidenceImage!.name}'),
                      onPressed: () async {
                        final image = await ImagePickerService()
                            .showImageSourceDialog(modalCtx);
                        if (image != null) {
                          modalSetState(() => evidenceImage = image);
                        }
                      },
                    ),

                    const SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                        backgroundColor: const Color(0xFF09090B),
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () async {
                        try {
                          final client = ref.read(apiClientProvider);
                          final position =
                              await AttendanceService.getCurrentPosition();
                          final formData = FormData.fromMap({
                            'subordinate_user_id':
                                _selectedSubordinate!['id'].toString(),
                            'outlet_id': outletId.toString(),
                            'notes': notesCtrl.text.trim(),
                            'no_order_reason': noOrderReasonCtrl.text.trim(),
                            if (selectedOrderId != null)
                              'linked_order_id': selectedOrderId.toString(),
                            'gps_lat': position.latitude.toString(),
                            'gps_lng': position.longitude.toString(),
                            if (evidenceImage != null)
                              'image': await MultipartFile.fromFile(
                                evidenceImage!.path,
                                filename: evidenceImage!.name,
                              ),
                          });
                          await client.dio.post(
                            '/visits/joint',
                            data: formData,
                            options:
                                Options(contentType: 'multipart/form-data'),
                          );
                          if (!modalCtx.mounted) return;
                          Navigator.pop(modalCtx);
                          _showToast(
                              'Joint Visit & Outcomes logged successfully!');
                        } catch (err) {
                          _showToast(
                              'Failed to record joint visit outcome: $err',
                              isError: true);
                        }
                      },
                      child: const Text('Submit Joint Visit Outcomes',
                          style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF09090B)),
          onPressed: () {
            if (_step > 1) {
              setState(() {
                _step -= 1;
                _showSearch = false;
                _outletQuery = '';
              });
            } else {
              context.pop();
            }
          },
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _step == 1
                  ? 'Select Subordinate Rep'
                  : _step == 2
                      ? 'Select Beat'
                      : 'Outlets (Joint Working)',
              style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                  color: Color(0xFF09090B)),
            ),
            if (_step == 3 && _selectedBeat != null)
              Text(
                'Beat: ${_selectedBeat!['name']}',
                style: const TextStyle(
                    fontSize: 11,
                    color: Color(0xFF71717A),
                    fontWeight: FontWeight.w600),
              ),
          ],
        ),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF09090B)))
          : _step == 1
              ? _buildStep1()
              : _step == 2
                  ? _buildStep2()
                  : _buildStep3(),
      bottomNavigationBar: _step == 3
          ? Container(
              decoration: const BoxDecoration(
                color: Colors.white,
                border:
                    Border(top: BorderSide(color: Color(0xFFE4E4E7), width: 1)),
              ),
              child: BottomNavigationBar(
                currentIndex: _viewMode,
                onTap: (index) => setState(() => _viewMode = index),
                backgroundColor: Colors.white,
                selectedItemColor: const Color(0xFF09090B),
                unselectedItemColor: const Color(0xFFA1A1AA),
                selectedLabelStyle:
                    const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                unselectedLabelStyle:
                    const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
                elevation: 0,
                items: const [
                  BottomNavigationBarItem(
                    icon: Icon(Icons.view_list_rounded),
                    activeIcon:
                        Icon(Icons.view_list_rounded, color: Color(0xFF09090B)),
                    label: 'List View',
                  ),
                  BottomNavigationBarItem(
                    icon: Icon(Icons.map_rounded),
                    activeIcon:
                        Icon(Icons.map_rounded, color: Color(0xFF09090B)),
                    label: 'Map View',
                  ),
                ],
              ),
            )
          : null,
      floatingActionButton: (_step == 3 && _viewMode == 0)
          ? FloatingActionButton.small(
              heroTag: 'fab_search_joint_outlets',
              backgroundColor: const Color(0xFFF4F4F5),
              foregroundColor: const Color(0xFF09090B),
              onPressed: () {
                setState(() {
                  _showSearch = !_showSearch;
                  if (!_showSearch) {
                    _searchCtrl.clear();
                    _outletQuery = '';
                  }
                });
              },
              tooltip: 'Search Outlets',
              child: Icon(_showSearch
                  ? Icons.search_off_rounded
                  : Icons.search_rounded),
            )
          : null,
    );
  }

  Widget _buildStep1() {
    if (_subordinates.isEmpty) {
      return const Center(
          child: Text('No subordinate field reps found in hierarchy.'));
    }
    final filtered = _subordinates.where((user) {
      if (_positionQuery.isEmpty) return true;
      final positions = (user['positions'] as List? ?? [])
          .map((p) => '${p['name']} ${p['code']}')
          .join(' ')
          .toLowerCase();
      return user['full_name']
              .toString()
              .toLowerCase()
              .contains(_positionQuery) ||
          positions.contains(_positionQuery);
    }).toList();
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: filtered.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (ctx, i) {
        if (i == 0) {
          return TextField(
            decoration: const InputDecoration(
              hintText: 'Search assigned L1 position or user...',
              prefixIcon: Icon(Icons.search_rounded),
              border: OutlineInputBorder(),
            ),
            onChanged: (value) =>
                setState(() => _positionQuery = value.trim().toLowerCase()),
          );
        }
        final user = filtered[i - 1];
        final positions = (user['positions'] as List? ?? []);
        return Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE4E4E7)),
          ),
          child: ListTile(
            leading: const CircleAvatar(
                backgroundColor: Color(0xFF09090B),
                child: Icon(Icons.person, color: Colors.white)),
            title: Text(user['full_name'],
                style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(
              positions.isEmpty
                  ? 'No assigned L1 position'
                  : positions
                      .map((p) =>
                          '${p['name']} (${p['code']}) · ${user['full_name']}')
                      .join('\n'),
            ),
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
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF4F4F5),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFE4E4E7)),
            ),
            child: Text(
              'Subordinate: ${_selectedSubordinate?['full_name']}',
              style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF09090B)),
            ),
          ),
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
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFFE4E4E7)),
                  ),
                  child: ListTile(
                    leading:
                        const Icon(Icons.map_rounded, color: Color(0xFF09090B)),
                    title: Text(beat['name'],
                        style: const TextStyle(fontWeight: FontWeight.bold)),
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
      ),
    );
  }

  Widget _buildStep3() {
    final filteredOutlets = _outlets.where((o) {
      if (_outletQuery.isEmpty) return true;
      final name = (o['name'] ?? '').toString().toLowerCase();
      final code = (o['code'] ?? '').toString().toLowerCase();
      final phone =
          (o['mobile_number'] ?? o['phone_number'] ?? o['mobile'] ?? '')
              .toString();
      final addr = (o['address'] ?? '').toString().toLowerCase();
      return name.contains(_outletQuery) ||
          code.contains(_outletQuery) ||
          phone.contains(_outletQuery) ||
          addr.contains(_outletQuery);
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_showSearch && _viewMode == 0)
          Container(
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: TextField(
              controller: _searchCtrl,
              onChanged: (val) =>
                  setState(() => _outletQuery = val.trim().toLowerCase()),
              decoration: InputDecoration(
                hintText: 'Search outlets by name, code, phone, or address...',
                hintStyle:
                    const TextStyle(fontSize: 13, color: Color(0xFFA1A1AA)),
                prefixIcon:
                    const Icon(Icons.search_rounded, color: Color(0xFF71717A)),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.clear_rounded, size: 18),
                  onPressed: () {
                    _searchCtrl.clear();
                    setState(() {
                      _outletQuery = '';
                      _showSearch = false;
                    });
                  },
                ),
                filled: true,
                fillColor: const Color(0xFFF4F4F5),
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
        Expanded(
          child: _viewMode == 0
              ? _buildListView(filteredOutlets)
              : _buildMapView(filteredOutlets),
        ),
      ],
    );
  }

  Widget _buildListView(List<dynamic> outlets) {
    if (outlets.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.storefront_rounded,
                size: 48, color: Color(0xFFA1A1AA)),
            const SizedBox(height: 12),
            Text(
              _outletQuery.isNotEmpty
                  ? 'No outlets match "$_outletQuery"'
                  : 'No active outlets found in this beat',
              style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                  color: Color(0xFF09090B)),
            ),
            const SizedBox(height: 4),
            const Text('Use the + New Outlet button to add new outlets.',
                style: TextStyle(fontSize: 12, color: Color(0xFF71717A))),
          ],
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: outlets.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (ctx, i) {
        final o = outlets[i];
        final phone = o['mobile_number'] ??
            o['phone_number'] ??
            o['mobile'] ??
            'No Phone';
        final code = o['code'] ?? 'OUT-${o['id']}';
        final channel = o['channel'] ?? 'GT';

        return Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE4E4E7), width: 1),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x04000000),
                  blurRadius: 6,
                  offset: Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        o['name'],
                        style: const TextStyle(
                          color: Color(0xFF09090B),
                          fontWeight: FontWeight.w800,
                          fontSize: 15,
                          letterSpacing: -0.3,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF4F4F5),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: const Color(0xFFE4E4E7)),
                      ),
                      child: Text(
                        code,
                        style: const TextStyle(
                          color: Color(0xFF3F3F46),
                          fontWeight: FontWeight.w700,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.phone_rounded,
                        size: 14, color: Color(0xFF2563EB)),
                    const SizedBox(width: 6),
                    Text(
                      phone.toString(),
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF2563EB),
                      ),
                    ),
                    if (o['contact_person'] != null ||
                        o['owner_name'] != null) ...[
                      const Text(' • ',
                          style: TextStyle(color: Color(0xFFA1A1AA))),
                      Expanded(
                        child: Text(
                          'Owner: ${o['contact_person'] ?? o['owner_name']}',
                          style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF71717A),
                              fontWeight: FontWeight.w500),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ],
                ),
                if (o['address'] != null &&
                    o['address'].toString().isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    o['address'].toString(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style:
                        const TextStyle(fontSize: 12, color: Color(0xFF71717A)),
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF4F4F5),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        channel.toString().toUpperCase(),
                        style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF52525B)),
                      ),
                    ),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF09090B),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(110, 36),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.assignment_turned_in_rounded,
                          size: 16),
                      label: const Text('Log Visit',
                          style: TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 12)),
                      onPressed: () => _submitJointVisit(o['id']),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildMapView(List<dynamic> outlets) {
    if (outlets.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24.0),
          child: Text(
            'No outlet map locations available for this beat.',
            style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 14,
                color: Color(0xFF71717A)),
          ),
        ),
      );
    }

    final selected =
        _selectedMapOutlet ?? outlets.first as Map<String, dynamic>;

    // Calculate mean center LatLng
    double sumLat = 0.0;
    double sumLng = 0.0;
    for (int i = 0; i < outlets.length; i++) {
      final o = outlets[i];
      sumLat +=
          double.parse((o['gps_lat'] ?? (12.9654 + (i * 0.01))).toString());
      sumLng +=
          double.parse((o['gps_lng'] ?? (80.2483 + (i * 0.01))).toString());
    }
    final centerLat = sumLat / outlets.length;
    final centerLng = sumLng / outlets.length;

    final markers = outlets.asMap().entries.map((entry) {
      final idx = entry.key;
      final outlet = entry.value as Map<String, dynamic>;
      final isSelected = selected['id'] == outlet['id'];

      final double lat = double.parse(
          (outlet['gps_lat'] ?? (12.9654 + (idx * 0.01))).toString());
      final double lng = double.parse(
          (outlet['gps_lng'] ?? (80.2483 + (idx * 0.01))).toString());

      return Marker(
        point: LatLng(lat, lng),
        width: 130,
        height: 70,
        child: GestureDetector(
          onTap: () {
            setState(() => _selectedMapOutlet = outlet);
            _openGoogleMaps(lat, lng, outlet['name'] ?? 'Outlet');
          },
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: isSelected
                      ? const Color(0xFFEA580C)
                      : const Color(0xFF09090B),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: isSelected
                          ? Colors.deepOrangeAccent.withValues(alpha: 0.4)
                          : Colors.black26,
                      blurRadius: isSelected ? 10 : 5,
                      spreadRadius: isSelected ? 3 : 1,
                    )
                  ],
                  border: Border.all(
                    color: Colors.white,
                    width: 2.5,
                  ),
                ),
                child: Icon(
                  Icons.location_on_rounded,
                  size: isSelected ? 22 : 16,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 2),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(6),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 2)
                  ],
                ),
                child: Text(
                  outlet['name'] ?? 'Outlet',
                  style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF09090B)),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      );
    }).toList();

    return SizedBox.expand(
      child: Column(
        children: [
          // Bounded Live OpenStreetMap Container View
          Expanded(
            child: Container(
              width: double.infinity,
              margin: const EdgeInsets.all(16),
              clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(
                color: const Color(0xFFE2E8F0),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFCBD5E1), width: 1.5),
              ),
              child: Stack(
                children: [
                  FlutterMap(
                    options: MapOptions(
                      initialCenter: LatLng(centerLat, centerLng),
                      initialZoom: 12.0,
                    ),
                    children: [
                      TileLayer(
                        urlTemplate:
                            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                        userAgentPackageName: 'com.safar.sfamobile',
                      ),
                      MarkerLayer(markers: markers),
                    ],
                  ),
                  Positioned(
                    top: 14,
                    left: 14,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: const [
                          BoxShadow(color: Colors.black12, blurRadius: 4)
                        ],
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.map_rounded,
                              size: 16, color: Color(0xFF2563EB)),
                          const SizedBox(width: 6),
                          Text(
                            'OpenStreetMap • ${outlets.length} Outlets',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                                color: Color(0xFF09090B)),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Bottom Interactive Details Callout Card
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE4E4E7)),
              boxShadow: const [
                BoxShadow(color: Colors.black12, blurRadius: 8)
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        selected['name'] ?? 'Outlet Details',
                        style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 15,
                            color: Color(0xFF09090B)),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF4F4F5),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        selected['code'] ?? 'OUT-${selected['id']}',
                        style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF52525B)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  selected['address'] ?? 'No address recorded',
                  style:
                      const TextStyle(fontSize: 12, color: Color(0xFF71717A)),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF2563EB),
                          side: const BorderSide(color: Color(0xFF2563EB)),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                        icon: const Icon(Icons.near_me_rounded, size: 16),
                        label: const Text('Google Maps',
                            style: TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 12)),
                        onPressed: () {
                          final double lat = double.parse(
                              (selected['gps_lat'] ?? 12.9654).toString());
                          final double lng = double.parse(
                              (selected['gps_lng'] ?? 80.2483).toString());
                          _openGoogleMaps(
                              lat, lng, selected['name'] ?? 'Outlet');
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF09090B),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                        icon: const Icon(Icons.assignment_turned_in_rounded,
                            size: 16),
                        label: const Text('Log Visit',
                            style: TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 12)),
                        onPressed: () => _submitJointVisit(selected['id']),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
