import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:geolocator/geolocator.dart';
import '../../providers/beat_provider.dart';
import '../../providers/attendance_provider.dart';
import '../../utils/haversine.dart';
import '../../models/outlet.dart';
import '../../services/attendance_service.dart';

class BeatPlanScreen extends ConsumerStatefulWidget {
  const BeatPlanScreen({super.key});

  @override
  ConsumerState<BeatPlanScreen> createState() => _BeatPlanScreenState();
}

class _BeatPlanScreenState extends ConsumerState<BeatPlanScreen> {
  Position? _currentPosition;

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  Future<void> _getCurrentLocation() async {
    try {
      final pos = await AttendanceService.getCurrentPosition();
      if (mounted) {
        setState(() {
          _currentPosition = pos;
        });
      }
    } catch (_) {}
  }

  void _showAddOptions(BuildContext context, List<Beat> beats, int? currentBeatId) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Select Action',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 20),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.map_rounded, color: Theme.of(context).colorScheme.primary),
                ),
                title: const Text('Create New Beat', style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('Add a new sales beat route'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showCreateBeatDialog();
                },
              ),
              const Divider(),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.storefront_rounded, color: Colors.green),
                ),
                title: const Text('Create New Outlet', style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('Register a customer shop at the current location'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showCreateOutletDialog(beats, currentBeatId);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showCreateBeatDialog() {
    final nameCtrl = TextEditingController();
    final codeCtrl = TextEditingController();
    String selectedType = 'GT';
    String? selectedGrade;
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Create New Beat'),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(labelText: 'Beat Name *', hintText: 'e.g. Downtown Route'),
                    validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: codeCtrl,
                    decoration: const InputDecoration(labelText: 'Beat Code *', hintText: 'e.g. BT_DOWNTOWN'),
                    validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: selectedType,
                    decoration: const InputDecoration(labelText: 'Beat Type *'),
                    items: const [
                      DropdownMenuItem(value: 'GT', child: Text('General Trade (GT)')),
                      DropdownMenuItem(value: 'MT', child: Text('Modern Trade (MT)')),
                      DropdownMenuItem(value: 'pharmacy', child: Text('Pharmacy')),
                      DropdownMenuItem(value: 'horeca', child: Text('HoReCa')),
                      DropdownMenuItem(value: 'institutional', child: Text('Institutional')),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (v) => setDialogState(() => selectedType = v!),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String?>(
                    value: selectedGrade,
                    decoration: const InputDecoration(labelText: 'Beat Grade (Optional)'),
                    items: const [
                      DropdownMenuItem(value: null, child: Text('None')),
                      DropdownMenuItem(value: 'Rural', child: Text('Rural')),
                      DropdownMenuItem(value: 'Urban', child: Text('Urban')),
                      DropdownMenuItem(value: 'Semi Urban', child: Text('Semi Urban')),
                      DropdownMenuItem(value: 'Metro', child: Text('Metro')),
                      DropdownMenuItem(value: 'Non-Metro', child: Text('Non-Metro')),
                    ],
                    onChanged: (v) => setDialogState(() => selectedGrade = v),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (formKey.currentState?.validate() == true) {
                  try {
                    final service = ref.read(masterServiceProvider);
                    final newBeat = await service.createBeat(
                      name: nameCtrl.text.trim(),
                      code: codeCtrl.text.trim(),
                      beatType: selectedType,
                      beatGrade: selectedGrade,
                    );
                    ref.invalidate(beatsProvider);
                    ref.read(selectedBeatIdProvider.notifier).state = newBeat.id;
                    if (mounted) {
                      Navigator.pop(ctx);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Beat "${newBeat.name}" created successfully.')),
                      );
                    }
                  } catch (e) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed to create beat: $e'), backgroundColor: Colors.red),
                    );
                  }
                }
              },
              child: const Text('Create'),
            ),
          ],
        ),
      ),
    );
  }

  void _showCreateOutletDialog(List<Beat> beats, int? currentBeatId) {
    if (beats.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please create a beat first.')),
      );
      return;
    }

    final nameCtrl = TextEditingController();
    final codeCtrl = TextEditingController();
    final ownerCtrl = TextEditingController();
    final mobileCtrl = TextEditingController();
    final addressCtrl = TextEditingController();
    final pincodeCtrl = TextEditingController();
    final gstinCtrl = TextEditingController();
    int selectedBeatId = currentBeatId ?? beats.first.id;
    String? selectedChannel;
    String? selectedShopType;
    bool attachGps = _currentPosition != null;
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Create New Outlet'),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(labelText: 'Outlet Name *', hintText: 'e.g. Apex Pharmacy'),
                    validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    value: selectedBeatId,
                    decoration: const InputDecoration(labelText: 'Assign Beat *'),
                    items: beats.map((b) => DropdownMenuItem(
                      value: b.id,
                      child: Text('${b.name} (${b.code})'),
                    )).toList(),
                    onChanged: (v) => setDialogState(() => selectedBeatId = v!),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: codeCtrl,
                    decoration: const InputDecoration(labelText: 'Outlet Code (Optional)', hintText: 'Auto-generated if empty'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: ownerCtrl,
                    decoration: const InputDecoration(labelText: 'Owner Name (Optional)', hintText: 'e.g. John Doe'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: mobileCtrl,
                    decoration: const InputDecoration(labelText: 'Mobile Number (Optional)', hintText: 'e.g. 9876543210'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: addressCtrl,
                    decoration: const InputDecoration(labelText: 'Address (Optional)'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: pincodeCtrl,
                    decoration: const InputDecoration(labelText: 'Pincode (Optional)'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: gstinCtrl,
                    decoration: const InputDecoration(labelText: 'GSTIN (Optional)'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String?>(
                    value: selectedChannel,
                    decoration: const InputDecoration(labelText: 'Channel (Optional)'),
                    items: const [
                      DropdownMenuItem(value: null, child: Text('None')),
                      DropdownMenuItem(value: 'GT', child: Text('General Trade (GT)')),
                      DropdownMenuItem(value: 'MT', child: Text('Modern Trade (MT)')),
                      DropdownMenuItem(value: 'pharmacy', child: Text('Pharmacy')),
                      DropdownMenuItem(value: 'horeca', child: Text('HoReCa')),
                      DropdownMenuItem(value: 'institutional', child: Text('Institutional')),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (v) => setDialogState(() => selectedChannel = v),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String?>(
                    value: selectedShopType,
                    decoration: const InputDecoration(labelText: 'Shop Type (Optional)'),
                    items: const [
                      DropdownMenuItem(value: null, child: Text('None')),
                      DropdownMenuItem(value: 'kirana', child: Text('Kirana')),
                      DropdownMenuItem(value: 'medical', child: Text('Medical')),
                      DropdownMenuItem(value: 'general', child: Text('General')),
                      DropdownMenuItem(value: 'supermarket', child: Text('Supermarket')),
                      DropdownMenuItem(value: 'hardware', child: Text('Hardware')),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (v) => setDialogState(() => selectedShopType = v),
                  ),
                  const SizedBox(height: 12),
                  if (_currentPosition != null)
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(
                        'Attach GPS Coordinates:\n(${_currentPosition!.latitude.toStringAsFixed(5)}, ${_currentPosition!.longitude.toStringAsFixed(5)})',
                        style: const TextStyle(fontSize: 12),
                      ),
                      value: attachGps,
                      onChanged: (v) => setDialogState(() => attachGps = v ?? false),
                    )
                  else
                    Row(
                      children: [
                        const Icon(Icons.gps_off_rounded, size: 16, color: Colors.orange),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'GPS coordinates not ready yet. Please ensure GPS is enabled.',
                            style: TextStyle(fontSize: 11, color: Colors.orange.shade800),
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (formKey.currentState?.validate() == true) {
                  try {
                    final service = ref.read(masterServiceProvider);
                    final newOutlet = await service.createOutlet(
                      name: nameCtrl.text.trim(),
                      beatId: selectedBeatId,
                      code: codeCtrl.text.trim(),
                      ownerName: ownerCtrl.text.trim(),
                      mobile: mobileCtrl.text.trim(),
                      address: addressCtrl.text.trim(),
                      pincode: pincodeCtrl.text.trim(),
                      gstin: gstinCtrl.text.trim(),
                      channel: selectedChannel,
                      shopType: selectedShopType,
                      gpsLat: attachGps ? _currentPosition?.latitude : null,
                      gpsLng: attachGps ? _currentPosition?.longitude : null,
                    );
                    ref.invalidate(beatPlanProvider(selectedBeatId));
                    if (mounted) {
                      Navigator.pop(ctx);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Outlet "${newOutlet.name}" created successfully.')),
                      );
                    }
                  } catch (e) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed to create outlet: $e'), backgroundColor: Colors.red),
                    );
                  }
                }
              },
              child: const Text('Create'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final beatsAsync = ref.watch(beatsProvider);
    final beatId = ref.watch(selectedBeatIdProvider);
    final beatPlanAsync = ref.watch(beatPlanProvider(beatId));
    final attendanceAsync = ref.watch(attendanceProvider);
    final theme = Theme.of(context);

    // Automatically set default selected beat once loaded
    beatsAsync.whenData((beats) {
      if (beatId == null && beats.isNotEmpty) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          ref.read(selectedBeatIdProvider.notifier).state = beats.first.id;
        });
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Beat Plan'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(beatsProvider);
              if (beatId != null) {
                ref.invalidate(beatPlanProvider(beatId));
              }
              _getCurrentLocation();
            },
          ),
        ],
      ),
      body: attendanceAsync.when(
        data: (att) {
          final isCheckedIn = att.checkedIn && att.isOpen;
          if (!isCheckedIn) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.warning_amber_rounded, size: 64, color: theme.colorScheme.error),
                    const SizedBox(height: 16),
                    Text(
                      'Workday Not Active',
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'You must Check In on the Dashboard before accessing your Beat Plan.',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: () => context.go('/home'),
                      child: const Text('Go to Dashboard'),
                    ),
                  ],
                ),
              ),
            );
          }

          return beatsAsync.when(
            data: (beats) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Dropdown Selector for Beat
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surface,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: theme.dividerColor, width: 1.0),
                        boxShadow: [
                          BoxShadow(
                            color: theme.colorScheme.shadow.withOpacity(0.02),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<int?>(
                          value: beatId,
                          hint: const Text('Select a sales beat route'),
                          isExpanded: true,
                          icon: const Icon(Icons.keyboard_arrow_down_rounded),
                          items: beats.map((b) => DropdownMenuItem<int?>(
                            value: b.id,
                            child: Text(
                              '${b.name} (${b.code})',
                              style: const TextStyle(fontWeight: FontWeight.bold),
                            ),
                          )).toList(),
                          onChanged: (v) {
                            ref.read(selectedBeatIdProvider.notifier).state = v;
                          },
                        ),
                      ),
                    ),
                  ),

                  // Beat Plan Details
                  Expanded(
                    child: beatPlanAsync.when(
                      data: (plan) {
                        final Beat? beat = plan['beat'];
                        final List<Outlet> outlets = plan['outlets'] ?? [];

                        if (beatId == null) {
                          return Center(
                            child: Text(
                              'Please select or create a beat.',
                              style: theme.textTheme.bodyMedium,
                            ),
                          );
                        }

                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (beat != null)
                              Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                                child: Container(
                                  padding: const EdgeInsets.all(16),
                                  decoration: BoxDecoration(
                                    color: theme.cardTheme.color,
                                    borderRadius: BorderRadius.circular(16),
                                    border: Border.all(color: theme.dividerColor, width: 1.0),
                                    boxShadow: [
                                      BoxShadow(
                                        color: theme.colorScheme.shadow.withOpacity(0.04),
                                        blurRadius: 10,
                                        offset: const Offset(0, 4),
                                      ),
                                    ],
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            beat.name,
                                            style: theme.textTheme.titleMedium?.copyWith(
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            beat.code,
                                            style: theme.textTheme.bodyMedium,
                                          ),
                                        ],
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                        decoration: BoxDecoration(
                                          color: theme.colorScheme.primary.withOpacity(0.1),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(
                                          beat.beatType,
                                          style: theme.textTheme.labelSmall?.copyWith(
                                            color: theme.colorScheme.primary,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            Expanded(
                              child: RefreshIndicator(
                                onRefresh: () async {
                                  ref.invalidate(beatsProvider);
                                  ref.invalidate(beatPlanProvider(beatId));
                                  await _getCurrentLocation();
                                },
                                child: outlets.isEmpty
                                    ? ListView(
                                        physics: const AlwaysScrollableScrollPhysics(),
                                        children: [
                                          SizedBox(height: MediaQuery.of(context).size.height * 0.2),
                                          Center(
                                            child: Text(
                                              'No outlets assigned to this beat.',
                                              style: theme.textTheme.bodyMedium,
                                            ),
                                          ),
                                        ],
                                      )
                                    : ListView.builder(
                                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                                        itemCount: outlets.length,
                                        itemBuilder: (ctx, index) {
                                          final outlet = outlets[index];
                                          double? dist;
                                          if (_currentPosition != null && outlet.hasGps) {
                                            dist = Haversine.distance(
                                              _currentPosition!.latitude,
                                              _currentPosition!.longitude,
                                              outlet.gpsLat!,
                                              outlet.gpsLng!,
                                            );
                                          }

                                          return Card(
                                            elevation: 2,
                                            shadowColor: theme.colorScheme.shadow.withOpacity(0.04),
                                            child: InkWell(
                                              onTap: () {
                                                ref.read(selectedOutletProvider.notifier).state = outlet;
                                                context.push('/outlet/${outlet.id}');
                                              },
                                              borderRadius: BorderRadius.circular(16),
                                              child: Padding(
                                                padding: const EdgeInsets.all(18.0),
                                                child: Column(
                                                  crossAxisAlignment: CrossAxisAlignment.start,
                                                  children: [
                                                    Row(
                                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                                      crossAxisAlignment: CrossAxisAlignment.start,
                                                      children: [
                                                        Expanded(
                                                          child: Column(
                                                            crossAxisAlignment: CrossAxisAlignment.start,
                                                            children: [
                                                              Text(
                                                                outlet.name,
                                                                style: theme.textTheme.titleMedium?.copyWith(
                                                                  fontWeight: FontWeight.bold,
                                                                ),
                                                              ),
                                                              const SizedBox(height: 4),
                                                              Text(
                                                                outlet.code,
                                                                style: theme.textTheme.bodyMedium,
                                                              ),
                                                            ],
                                                          ),
                                                        ),
                                                        Container(
                                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                                          decoration: BoxDecoration(
                                                            color: theme.colorScheme.primary.withOpacity(0.08),
                                                            borderRadius: BorderRadius.circular(6),
                                                          ),
                                                          child: Text(
                                                            outlet.channelLabel,
                                                            style: theme.textTheme.labelSmall?.copyWith(
                                                              color: theme.colorScheme.primary,
                                                              fontWeight: FontWeight.bold,
                                                              fontSize: 10,
                                                            ),
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                    const SizedBox(height: 12),
                                                    if (outlet.address != null)
                                                      Text(
                                                        outlet.address!,
                                                        maxLines: 2,
                                                        overflow: TextOverflow.ellipsis,
                                                        style: theme.textTheme.bodyMedium,
                                                      ),
                                                    const SizedBox(height: 16),
                                                    Row(
                                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                                      children: [
                                                        if (dist != null)
                                                          Row(
                                                            children: [
                                                              Icon(Icons.location_on_rounded, color: theme.colorScheme.primary, size: 16),
                                                              const SizedBox(width: 4),
                                                              Text(
                                                                dist < 1000
                                                                    ? '${dist.toStringAsFixed(0)} m'
                                                                    : '${(dist / 1000).toStringAsFixed(1)} km',
                                                                style: theme.textTheme.bodyMedium?.copyWith(
                                                                  color: theme.colorScheme.primary,
                                                                  fontWeight: FontWeight.bold,
                                                                ),
                                                              ),
                                                            ],
                                                          )
                                                        else
                                                          const SizedBox(),
                                                        Row(
                                                          children: [
                                                            Text(
                                                              'View Details',
                                                              style: theme.textTheme.bodyMedium?.copyWith(
                                                                color: theme.colorScheme.primary,
                                                                fontWeight: FontWeight.bold,
                                                              ),
                                                            ),
                                                            const SizedBox(width: 4),
                                                            Icon(
                                                              Icons.arrow_forward_rounded,
                                                              color: theme.colorScheme.primary,
                                                              size: 14,
                                                            ),
                                                          ],
                                                        ),
                                                      ],
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ),
                                          );
                                        },
                                      ),
                              ),
                            ),
                          ],
                        );
                      },
                      loading: () => const Center(child: CircularProgressIndicator()),
                      error: (e, __) => Center(child: Text('Error loading beat plan: $e')),
                    ),
                  ),
                ],
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, __) => Center(child: Text('Error loading beats: $e')),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, __) => Center(child: Text('Error: $e')),
      ),
      floatingActionButton: beatId != null
          ? beatsAsync.maybeWhen(
              data: (beats) => FloatingActionButton(
                onPressed: () => _showAddOptions(context, beats, beatId),
                tooltip: 'Add Beat or Outlet',
                child: const Icon(Icons.add),
              ),
              orElse: () => null,
            )
          : null,
    );
  }
}
