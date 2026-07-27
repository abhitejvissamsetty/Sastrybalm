import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:geolocator/geolocator.dart';
import '../../providers/beat_provider.dart';
import '../../models/outlet.dart';
import '../../services/attendance_service.dart';

class OutletCreateScreen extends ConsumerStatefulWidget {
  const OutletCreateScreen({super.key});

  @override
  ConsumerState<OutletCreateScreen> createState() => _OutletCreateScreenState();
}

class _OutletCreateScreenState extends ConsumerState<OutletCreateScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _ownerCtrl = TextEditingController();
  final _mobileCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();
  final _pincodeCtrl = TextEditingController();
  final _gstinCtrl = TextEditingController();

  int? _selectedBeatId;
  String? _selectedChannel;
  String? _selectedShopType;
  Position? _currentPosition;
  bool _attachGps = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _codeCtrl.dispose();
    _ownerCtrl.dispose();
    _mobileCtrl.dispose();
    _addressCtrl.dispose();
    _pincodeCtrl.dispose();
    _gstinCtrl.dispose();
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

  Future<void> _submitForm() async {
    if (_formKey.currentState?.validate() != true) return;
    if (_selectedBeatId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a beat to assign this outlet.')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final service = ref.read(masterServiceProvider);
      final newOutlet = await service.createOutlet(
        name: _nameCtrl.text.trim(),
        beatId: _selectedBeatId!,
        code: _codeCtrl.text.trim().isNotEmpty ? _codeCtrl.text.trim() : null,
        ownerName: _ownerCtrl.text.trim().isNotEmpty ? _ownerCtrl.text.trim() : null,
        mobile: _mobileCtrl.text.trim().isNotEmpty ? _mobileCtrl.text.trim() : null,
        address: _addressCtrl.text.trim().isNotEmpty ? _addressCtrl.text.trim() : null,
        pincode: _pincodeCtrl.text.trim().isNotEmpty ? _pincodeCtrl.text.trim() : null,
        gstin: _gstinCtrl.text.trim().isNotEmpty ? _gstinCtrl.text.trim() : null,
        channel: _selectedChannel,
        shopType: _selectedShopType,
        gpsLat: _attachGps ? _currentPosition?.latitude : null,
        gpsLng: _attachGps ? _currentPosition?.longitude : null,
      );

      ref.invalidate(beatPlanProvider(_selectedBeatId));
      ref.invalidate(beatsProvider);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Outlet "${newOutlet.name}" created successfully!'),
            backgroundColor: const Color(0xFF16A34A),
            behavior: SnackBarBehavior.floating,
          ),
        );
        context.pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to create outlet: $e'),
            backgroundColor: const Color(0xFFDC2626),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final beatsAsync = ref.watch(beatsProvider);
    final currentBeatId = ref.watch(selectedBeatIdProvider);

    // Default pre-selection for beat
    if (_selectedBeatId == null && currentBeatId != null) {
      _selectedBeatId = currentBeatId;
    }

    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF09090B)),
          onPressed: () => context.pop(),
        ),
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Create New Outlet',
              style: TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 17,
                color: Color(0xFF09090B),
                letterSpacing: -0.4,
              ),
            ),
            Text(
              'Register a customer shop on your beat route',
              style: TextStyle(fontSize: 11, color: Color(0xFF71717A)),
            ),
          ],
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Form Card Container
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFE4E4E7)),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x04000000),
                      blurRadius: 8,
                      offset: Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Outlet Information',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF09090B),
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Outlet Name Field
                    _buildTextField(
                      controller: _nameCtrl,
                      label: 'Outlet Name *',
                      hint: 'e.g. Apex Pharmacy',
                      validator: (v) => v == null || v.trim().isEmpty ? 'Outlet name is required' : null,
                    ),
                    const SizedBox(height: 14),

                    // Assign Beat Dropdown
                    beatsAsync.when(
                      data: (beats) {
                        if (beats.isNotEmpty && _selectedBeatId == null) {
                          _selectedBeatId = beats.first.id;
                        }
                        return _buildDropdownField<int?>(
                          value: _selectedBeatId,
                          label: 'Assign Beat *',
                          items: beats.map((b) => DropdownMenuItem<int?>(
                            value: b.id,
                            child: Text('${b.name} (${b.code})', overflow: TextOverflow.ellipsis),
                          )).toList(),
                          onChanged: (v) => setState(() => _selectedBeatId = v),
                          validator: (v) => v == null ? 'Beat assignment is required' : null,
                        );
                      },
                      loading: () => const LinearProgressIndicator(color: Color(0xFF09090B)),
                      error: (e, _) => Text('Error loading beats: $e', style: const TextStyle(color: Colors.red)),
                    ),
                    const SizedBox(height: 14),

                    // Outlet Code Field
                    _buildTextField(
                      controller: _codeCtrl,
                      label: 'Outlet Code (Optional)',
                      hint: 'Auto-generated if left empty',
                    ),
                    const SizedBox(height: 14),

                    // Owner Name Field
                    _buildTextField(
                      controller: _ownerCtrl,
                      label: 'Owner Name (Optional)',
                      hint: 'e.g. Ramesh Kumar',
                    ),
                    const SizedBox(height: 14),

                    // Mobile Number Field
                    _buildTextField(
                      controller: _mobileCtrl,
                      label: 'Mobile / Phone Number (Optional)',
                      hint: 'e.g. 9876543210',
                      keyboardType: TextInputType.phone,
                    ),
                    const SizedBox(height: 14),

                    // Address Field
                    _buildTextField(
                      controller: _addressCtrl,
                      label: 'Address (Optional)',
                      hint: 'Street, Area, Landmark',
                      maxLines: 2,
                    ),
                    const SizedBox(height: 14),

                    // Pincode Field
                    _buildTextField(
                      controller: _pincodeCtrl,
                      label: 'Pincode (Optional)',
                      hint: 'e.g. 600028',
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 14),

                    // GSTIN Field
                    _buildTextField(
                      controller: _gstinCtrl,
                      label: 'GSTIN (Optional)',
                      hint: 'e.g. 33AAAAA0000A1Z5',
                    ),
                    const SizedBox(height: 14),

                    // Channel Dropdown
                    _buildDropdownField<String?>(
                      value: _selectedChannel,
                      label: 'Channel (Optional)',
                      items: const [
                        DropdownMenuItem(value: null, child: Text('None / Default')),
                        DropdownMenuItem(value: 'GT', child: Text('General Trade (GT)')),
                        DropdownMenuItem(value: 'MT', child: Text('Modern Trade (MT)')),
                        DropdownMenuItem(value: 'pharmacy', child: Text('Pharmacy')),
                        DropdownMenuItem(value: 'horeca', child: Text('HoReCa')),
                        DropdownMenuItem(value: 'institutional', child: Text('Institutional')),
                        DropdownMenuItem(value: 'other', child: Text('Other')),
                      ],
                      onChanged: (v) => setState(() => _selectedChannel = v),
                    ),
                    const SizedBox(height: 14),

                    // Shop Type Dropdown
                    _buildDropdownField<String?>(
                      value: _selectedShopType,
                      label: 'Shop Type (Optional)',
                      items: const [
                        DropdownMenuItem(value: null, child: Text('None / Default')),
                        DropdownMenuItem(value: 'kirana', child: Text('Kirana Store')),
                        DropdownMenuItem(value: 'medical', child: Text('Medical / Chemist')),
                        DropdownMenuItem(value: 'general', child: Text('General Store')),
                        DropdownMenuItem(value: 'supermarket', child: Text('Supermarket')),
                        DropdownMenuItem(value: 'hardware', child: Text('Hardware Store')),
                        DropdownMenuItem(value: 'other', child: Text('Other')),
                      ],
                      onChanged: (v) => setState(() => _selectedShopType = v),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // GPS Location Attachment Box
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFE4E4E7)),
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: _currentPosition != null ? const Color(0xFFEFF6FF) : const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _currentPosition != null ? Icons.my_location_rounded : Icons.location_off_rounded,
                        color: _currentPosition != null ? const Color(0xFF2563EB) : const Color(0xFFDC2626),
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _currentPosition != null ? 'GPS Location Acquired' : 'GPS Coordinates Pending',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF09090B),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _currentPosition != null
                                ? 'Lat: ${_currentPosition!.latitude.toStringAsFixed(5)}, Lng: ${_currentPosition!.longitude.toStringAsFixed(5)}'
                                : 'Ensure device location is enabled for shop tagging.',
                            style: TextStyle(
                              fontSize: 11,
                              color: _currentPosition != null ? const Color(0xFF2563EB) : const Color(0xFF71717A),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (_currentPosition != null)
                      Switch.adaptive(
                        value: _attachGps,
                        activeColor: const Color(0xFF09090B),
                        onChanged: (v) => setState(() => _attachGps = v),
                      ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Submit Button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF09090B),
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 50),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    elevation: 0,
                  ),
                  icon: _isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.check_circle_rounded, size: 20),
                  label: Text(
                    _isSubmitting ? 'Creating Outlet...' : 'Create Outlet Now',
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
                  ),
                  onPressed: _isSubmitting ? null : _submitForm,
                ),
              ),
              const SizedBox(height: 30),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    String? hint,
    TextInputType keyboardType = TextInputType.text,
    int maxLines = 1,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Color(0xFF3F3F46),
          ),
        ),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          maxLines: maxLines,
          validator: validator,
          style: const TextStyle(fontSize: 13, color: Color(0xFF09090B), fontWeight: FontWeight.w600),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(fontSize: 13, color: Color(0xFFA1A1AA), fontWeight: FontWeight.w400),
            filled: true,
            fillColor: const Color(0xFFF4F4F5),
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDropdownField<T>({
    required T value,
    required String label,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
    String? Function(T?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Color(0xFF3F3F46),
          ),
        ),
        const SizedBox(height: 6),
        DropdownButtonFormField<T>(
          value: value,
          items: items,
          onChanged: onChanged,
          validator: validator,
          isExpanded: true,
          style: const TextStyle(fontSize: 13, color: Color(0xFF09090B), fontWeight: FontWeight.w600),
          decoration: InputDecoration(
            filled: true,
            fillColor: const Color(0xFFF4F4F5),
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }
}
