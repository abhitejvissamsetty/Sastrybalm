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
  bool _showSearch = false;
  final _searchCtrl = TextEditingController();
  String _outletQuery = '';

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
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
    context.push('/outlet/new');
  }

  @override
  Widget build(BuildContext context) {
    final beatsAsync = ref.watch(beatsProvider);
    final beatId = ref.watch(selectedBeatIdProvider);
    final beatPlanAsync = ref.watch(beatPlanProvider(beatId));
    final attendanceAsync = ref.watch(attendanceProvider);
    final theme = Theme.of(context);

    beatsAsync.whenData((beats) {
      if (beatId == null && beats.isNotEmpty) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          ref.read(selectedBeatIdProvider.notifier).state = beats.first.id;
        });
      }
    });

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF09090B)),
          onPressed: () => context.pop(),
        ),
        title: beatsAsync.maybeWhen(
          data: (beats) {
            final currentBeat = beats.firstWhere((b) => b.id == beatId, orElse: () => beats.isNotEmpty ? beats.first : Beat(id: 0, name: 'Beat Route', code: '', beatType: 'GT', outlets: []));
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  currentBeat.name,
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: Color(0xFF09090B)),
                ),
                Text(
                  currentBeat.code.isNotEmpty ? 'Code: ${currentBeat.code}' : 'Beat Outlets Route',
                  style: const TextStyle(fontSize: 11, color: Color(0xFF71717A)),
                ),
              ],
            );
          },
          orElse: () => const Text('Beat Outlets Route', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF09090B))),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF09090B)),
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
                      style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'You must Check In on the Dashboard before accessing beat outlets.',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF09090B),
                        foregroundColor: Colors.white,
                      ),
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
                  // Inline Search Input Bar (when toggled via FAB)
                  if (_showSearch)
                    Container(
                      color: Colors.white,
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                      child: TextField(
                        controller: _searchCtrl,
                        onChanged: (val) => setState(() => _outletQuery = val.trim().toLowerCase()),
                        decoration: InputDecoration(
                          hintText: 'Search outlets by name, code, phone, or owner...',
                          hintStyle: const TextStyle(fontSize: 13, color: Color(0xFFA1A1AA)),
                          prefixIcon: const Icon(Icons.search_rounded, color: Color(0xFF71717A)),
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

                  // Beat Outlets Content
                  Expanded(
                    child: beatPlanAsync.when(
                      data: (plan) {
                        final Beat? beat = plan['beat'];
                        final List<Outlet> allOutlets = plan['outlets'] ?? [];
                        final outlets = allOutlets.where((o) {
                          if (_outletQuery.isEmpty) return true;
                          final nameMatch = o.name.toLowerCase().contains(_outletQuery);
                          final codeMatch = o.code.toLowerCase().contains(_outletQuery);
                          final mobileMatch = (o.mobile ?? '').contains(_outletQuery);
                          final ownerMatch = (o.ownerName ?? '').toLowerCase().contains(_outletQuery);
                          return nameMatch || codeMatch || mobileMatch || ownerMatch;
                        }).toList();

                        if (beatId == null) {
                          return const Center(child: Text('Please select an active beat.'));
                        }

                        return RefreshIndicator(
                          color: const Color(0xFF09090B),
                          onRefresh: () async {
                            ref.invalidate(beatsProvider);
                            ref.invalidate(beatPlanProvider(beatId));
                            await _getCurrentLocation();
                          },
                          child: outlets.isEmpty
                              ? ListView(
                                  physics: const AlwaysScrollableScrollPhysics(),
                                  children: [
                                    SizedBox(height: MediaQuery.of(context).size.height * 0.25),
                                    Center(
                                      child: Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          const Icon(Icons.storefront_rounded, size: 48, color: Color(0xFFA1A1AA)),
                                          const SizedBox(height: 12),
                                          Text(
                                            _outletQuery.isNotEmpty ? 'No outlets match "$_outletQuery"' : 'No active outlets in this beat',
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF09090B)),
                                          ),
                                          const SizedBox(height: 4),
                                          const Text('Use the + New Outlet button to add customer outlets.', style: TextStyle(fontSize: 12, color: Color(0xFF71717A))),
                                        ],
                                      ),
                                    ),
                                  ],
                                )
                              : ListView.separated(
                                  padding: const EdgeInsets.all(16),
                                  itemCount: outlets.length,
                                  separatorBuilder: (_, __) => const SizedBox(height: 12),
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

                                    return Material(
                                      color: Colors.white,
                                      borderRadius: BorderRadius.circular(16),
                                      child: InkWell(
                                        onTap: () {
                                          ref.read(selectedOutletProvider.notifier).state = outlet;
                                          context.push('/outlet/${outlet.id}');
                                        },
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
                                                      outlet.name,
                                                      style: const TextStyle(
                                                        color: Color(0xFF09090B),
                                                        fontWeight: FontWeight.w800,
                                                        fontSize: 15,
                                                        letterSpacing: -0.3,
                                                      ),
                                                    ),
                                                  ),
                                                  Container(
                                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                                    decoration: BoxDecoration(
                                                      color: const Color(0xFFF4F4F5),
                                                      borderRadius: BorderRadius.circular(6),
                                                      border: Border.all(color: const Color(0xFFE4E4E7)),
                                                    ),
                                                    child: Text(
                                                      outlet.code.isNotEmpty ? outlet.code : 'OUT-${outlet.id}',
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
                                              // Phone Number & Owner Details
                                              Row(
                                                children: [
                                                  const Icon(Icons.phone_rounded, size: 14, color: Color(0xFF2563EB)),
                                                  const SizedBox(width: 6),
                                                  Text(
                                                    outlet.mobile != null && outlet.mobile!.isNotEmpty ? outlet.mobile! : 'No Phone Number',
                                                    style: TextStyle(
                                                      fontSize: 13,
                                                      fontWeight: FontWeight.w700,
                                                      color: outlet.mobile != null && outlet.mobile!.isNotEmpty ? const Color(0xFF2563EB) : const Color(0xFFA1A1AA),
                                                    ),
                                                  ),
                                                  if (outlet.ownerName != null && outlet.ownerName!.isNotEmpty) ...[
                                                    const Text(' • ', style: TextStyle(color: Color(0xFFA1A1AA))),
                                                    Expanded(
                                                      child: Text(
                                                        'Owner: ${outlet.ownerName}',
                                                        style: const TextStyle(fontSize: 12, color: Color(0xFF71717A), fontWeight: FontWeight.w500),
                                                        maxLines: 1,
                                                        overflow: TextOverflow.ellipsis,
                                                      ),
                                                    ),
                                                  ],
                                                ],
                                              ),
                                              if (outlet.address != null && outlet.address!.isNotEmpty) ...[
                                                const SizedBox(height: 6),
                                                Text(
                                                  outlet.address!,
                                                  maxLines: 1,
                                                  overflow: TextOverflow.ellipsis,
                                                  style: const TextStyle(fontSize: 12, color: Color(0xFF71717A)),
                                                ),
                                              ],
                                              const SizedBox(height: 12),
                                              Row(
                                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                                children: [
                                                  Row(
                                                    children: [
                                                      Container(
                                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                                        decoration: BoxDecoration(
                                                          color: const Color(0xFFF4F4F5),
                                                          borderRadius: BorderRadius.circular(6),
                                                        ),
                                                        child: Text(
                                                          outlet.channelLabel,
                                                          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF52525B)),
                                                        ),
                                                      ),
                                                      if (dist != null) ...[
                                                        const SizedBox(width: 8),
                                                        Row(
                                                          children: [
                                                            const Icon(Icons.location_on_rounded, color: Color(0xFF2563EB), size: 14),
                                                            const SizedBox(width: 3),
                                                            Text(
                                                              dist < 1000 ? '${dist.toStringAsFixed(0)} m' : '${(dist / 1000).toStringAsFixed(1)} km',
                                                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF2563EB)),
                                                            ),
                                                          ],
                                                        ),
                                                      ],
                                                    ],
                                                  ),
                                                  Row(
                                                    children: const [
                                                      Text(
                                                        'Visit Outlet',
                                                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF09090B)),
                                                      ),
                                                      SizedBox(width: 4),
                                                      Icon(Icons.arrow_forward_ios_rounded, size: 12, color: Color(0xFF09090B)),
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
                        );
                      },
                      loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
                      error: (e, __) => Center(child: Text('Error loading beat plan: $e')),
                    ),
                  ),
                ],
              );
            },
            loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
            error: (e, __) => Center(child: Text('Error loading beats: $e')),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF09090B))),
        error: (e, __) => Center(child: Text('Error: $e')),
      ),
      floatingActionButton: beatId != null
          ? beatsAsync.maybeWhen(
              data: (beats) => Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FloatingActionButton.small(
                    heroTag: 'fab_search_outlets',
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
                    child: Icon(_showSearch ? Icons.search_off_rounded : Icons.search_rounded),
                  ),
                  const SizedBox(width: 10),
                  FloatingActionButton.extended(
                    heroTag: 'fab_create_outlet',
                    backgroundColor: const Color(0xFF09090B),
                    foregroundColor: Colors.white,
                    onPressed: () => _showAddOptions(context, beats, beatId),
                    icon: const Icon(Icons.add_location_alt_rounded, size: 18),
                    label: const Text('New Outlet', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  ),
                ],
              ),
              orElse: () => null,
            )
          : null,
    );
  }
}
