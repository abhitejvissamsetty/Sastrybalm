import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/beat_provider.dart';
import '../../services/attendance_service.dart';

class OutletCreateScreen extends ConsumerStatefulWidget {
  const OutletCreateScreen({super.key});

  @override
  ConsumerState<OutletCreateScreen> createState() => _OutletCreateScreenState();
}

class _OutletCreateScreenState extends ConsumerState<OutletCreateScreen> {
  final _formKeyStep1 = GlobalKey<FormState>();
  final _formKeyStep2 = GlobalKey<FormState>();
  final _formKeyStep3 = GlobalKey<FormState>();

  final _nameCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _ownerCtrl = TextEditingController();
  final _mobileCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();
  final _pincodeCtrl = TextEditingController();
  final _gstinCtrl = TextEditingController();

  int _currentStep = 0; // 0: Basic Info, 1: Contact & Address, 2: Trade & Location

  int? _selectedBeatId;
  String? _selectedChannel;
  String? _selectedShopType;
  Position? _currentPosition;
  File? _outletPhoto;
  final _picker = ImagePicker();
  bool _attachGps = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final picked = await _picker.pickImage(source: source, imageQuality: 75);
      if (picked != null) {
        setState(() {
          _outletPhoto = File(picked.path);
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error selecting photo: $e')),
        );
      }
    }
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

  void _nextStep() {
    if (_currentStep == 0) {
      if (_formKeyStep1.currentState?.validate() != true) return;
      if (_selectedBeatId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please select a beat to assign this outlet.')),
        );
        return;
      }
      setState(() => _currentStep = 1);
    } else if (_currentStep == 1) {
      if (_formKeyStep2.currentState?.validate() != true) return;
      setState(() => _currentStep = 2);
    } else if (_currentStep == 2) {
      _submitForm();
    }
  }

  void _prevStep() {
    if (_currentStep > 0) {
      setState(() => _currentStep -= 1);
    } else {
      context.pop();
    }
  }

  Future<void> _submitForm() async {
    if (_selectedBeatId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a beat to assign this outlet.')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final service = ref.read(masterServiceProvider);
      String? photoS3Url;

      if (_outletPhoto != null) {
        photoS3Url = await service.uploadOutletPhoto(_outletPhoto!);
      }

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
        photoUrl: photoS3Url,
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
          onPressed: _prevStep,
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Create New Outlet',
              style: TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 17,
                color: Color(0xFF09090B),
                letterSpacing: -0.4,
              ),
            ),
            Text(
              'Step ${_currentStep + 1} of 3 — ${_getStepTitle(_currentStep)}',
              style: const TextStyle(fontSize: 11, color: Color(0xFF71717A), fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Step Progress Bar Indicator
          _buildStepHeaderIndicator(),

          // Main Step Form Content
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: _buildCurrentStepView(beatsAsync),
            ),
          ),
        ],
      ),
      bottomNavigationBar: _buildBottomWizardNav(),
    );
  }

  String _getStepTitle(int step) {
    switch (step) {
      case 0:
        return 'Basic & Beat Info';
      case 1:
        return 'Owner & Contact Details';
      case 2:
        return 'Trade Type & GPS Tagging';
      default:
        return '';
    }
  }

  Widget _buildStepHeaderIndicator() {
    final stepTitles = ['Basic Info', 'Contact Info', 'Trade & GPS'];
    final stepIcons = [
      Icons.storefront_rounded,
      Icons.person_pin_circle_rounded,
      Icons.assignment_turned_in_rounded,
    ];

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(color: Color(0xFFE4E4E7), width: 1),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Segmented Progress Bar
          Row(
            children: List.generate(3, (index) {
              final isCompleted = _currentStep > index;
              final isCurrent = _currentStep == index;
              return Expanded(
                child: Container(
                  height: 4,
                  margin: EdgeInsets.only(right: index < 2 ? 6 : 0),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(2),
                    color: isCompleted
                        ? const Color(0xFF16A34A)
                        : isCurrent
                            ? const Color(0xFF09090B)
                            : const Color(0xFFE4E4E7),
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 12),

          // Step Pills Row
          Row(
            children: List.generate(3, (index) {
              final isCompleted = _currentStep > index;
              final isCurrent = _currentStep == index;
              return Expanded(
                child: GestureDetector(
                  onTap: () {
                    if (index < _currentStep) {
                      setState(() => _currentStep = index);
                    }
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
                    margin: EdgeInsets.only(right: index < 2 ? 6 : 0),
                    decoration: BoxDecoration(
                      color: isCurrent
                          ? const Color(0xFF09090B)
                          : isCompleted
                              ? const Color(0xFFF0FDF4)
                              : const Color(0xFFF4F4F5),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isCurrent
                            ? const Color(0xFF09090B)
                            : isCompleted
                                ? const Color(0xFFBBF7D0)
                                : const Color(0xFFE4E4E7),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          isCompleted ? Icons.check_circle_rounded : stepIcons[index],
                          size: 14,
                          color: isCurrent
                              ? Colors.white
                              : isCompleted
                                  ? const Color(0xFF16A34A)
                                  : const Color(0xFF71717A),
                        ),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            stepTitles[index],
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: isCurrent || isCompleted
                                  ? FontWeight.w700
                                  : FontWeight.w500,
                              color: isCurrent
                                  ? Colors.white
                                  : isCompleted
                                      ? const Color(0xFF15803D)
                                      : const Color(0xFF71717A),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }

  Widget _buildCurrentStepView(AsyncValue<List<dynamic>> beatsAsync) {
    switch (_currentStep) {
      case 0:
        return Form(
          key: _formKeyStep1,
          child: Container(
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
                  'Step 1: Basic & Beat Assignment',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF09090B),
                  ),
                ),
                const SizedBox(height: 16),
                _buildTextField(
                  controller: _nameCtrl,
                  label: 'Outlet Name *',
                  hint: 'e.g. Apex Pharmacy',
                  validator: (v) => v == null || v.trim().isEmpty ? 'Outlet name is required' : null,
                ),
                const SizedBox(height: 14),
                beatsAsync.when(
                  data: (beats) {
                    if (beats.isNotEmpty && _selectedBeatId == null) {
                      _selectedBeatId = beats.first.id;
                    }
                    return _buildDropdownField<int?>(
                      value: _selectedBeatId,
                      label: 'Assign Beat *',
                      items: beats
                          .map((b) => DropdownMenuItem<int?>(
                                value: b.id,
                                child: Text('${b.name} (${b.code})', overflow: TextOverflow.ellipsis),
                              ))
                          .toList(),
                      onChanged: (v) => setState(() => _selectedBeatId = v),
                      validator: (v) => v == null ? 'Beat assignment is required' : null,
                    );
                  },
                  loading: () => const LinearProgressIndicator(color: Color(0xFF09090B)),
                  error: (e, _) => Text('Error loading beats: $e', style: const TextStyle(color: Colors.red)),
                ),
                const SizedBox(height: 14),
                _buildTextField(
                  controller: _codeCtrl,
                  label: 'Outlet Code (Optional)',
                  hint: 'Auto-generated if left empty',
                ),
              ],
            ),
          ),
        );
      case 1:
        return Form(
          key: _formKeyStep2,
          child: Container(
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
                  'Step 2: Owner & Contact Info',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF09090B),
                  ),
                ),
                const SizedBox(height: 16),
                _buildTextField(
                  controller: _ownerCtrl,
                  label: 'Owner Name (Optional)',
                  hint: 'e.g. Ramesh Kumar',
                ),
                const SizedBox(height: 14),
                _buildTextField(
                  controller: _mobileCtrl,
                  label: 'Mobile / Phone Number (Optional)',
                  hint: 'e.g. 9876543210',
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 14),
                _buildTextField(
                  controller: _addressCtrl,
                  label: 'Address (Optional)',
                  hint: 'Street, Area, Landmark',
                  maxLines: 2,
                ),
                const SizedBox(height: 14),
                _buildTextField(
                  controller: _pincodeCtrl,
                  label: 'Pincode (Optional)',
                  hint: 'e.g. 600028',
                  keyboardType: TextInputType.number,
                ),
              ],
            ),
          ),
        );
      case 2:
        return Form(
          key: _formKeyStep3,
          child: Column(
            children: [
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
                      'Step 3: Trade & Tax Classification',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF09090B),
                      ),
                    ),
                    const SizedBox(height: 16),
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
                    const SizedBox(height: 14),
                    _buildTextField(
                      controller: _gstinCtrl,
                      label: 'GSTIN (Optional)',
                      hint: 'e.g. 33AAAAA0000A1Z5',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Outlet Storefront Photo Attachment Card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFE4E4E7)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.add_a_photo_rounded, size: 18, color: Color(0xFF09090B)),
                        SizedBox(width: 8),
                        Text(
                          'Storefront / Outlet Photo (Optional)',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF09090B),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_outletPhoto != null)
                      Stack(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.file(
                              _outletPhoto!,
                              height: 140,
                              width: double.infinity,
                              fit: BoxFit.cover,
                            ),
                          ),
                          Positioned(
                            top: 8,
                            right: 8,
                            child: GestureDetector(
                              onTap: () => setState(() => _outletPhoto = null),
                              child: Container(
                                padding: const EdgeInsets.all(6),
                                decoration: const BoxDecoration(
                                  color: Colors.black54,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(Icons.close_rounded, size: 16, color: Colors.white),
                              ),
                            ),
                          ),
                        ],
                      )
                    else
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                foregroundColor: const Color(0xFF09090B),
                                side: const BorderSide(color: Color(0xFFE4E4E7)),
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              ),
                              onPressed: () => _pickImage(ImageSource.camera),
                              icon: const Icon(Icons.camera_alt_rounded, size: 18),
                              label: const Text('Camera', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                foregroundColor: const Color(0xFF09090B),
                                side: const BorderSide(color: Color(0xFFE4E4E7)),
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              ),
                              onPressed: () => _pickImage(ImageSource.gallery),
                              icon: const Icon(Icons.photo_library_rounded, size: 18),
                              label: const Text('Gallery', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // GPS Location Attachment Card
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
                        activeThumbColor: const Color(0xFF09090B),
                        onChanged: (v) => setState(() => _attachGps = v),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      default:
        return const SizedBox();
    }
  }

  Widget _buildBottomWizardNav() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Color(0xFFE4E4E7), width: 1)),
      ),
      child: Row(
        children: [
          if (_currentStep > 0)
            Expanded(
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF09090B),
                  side: const BorderSide(color: Color(0xFFE4E4E7)),
                  minimumSize: const Size(double.infinity, 48),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _prevStep,
                child: const Text('Back', style: TextStyle(fontWeight: FontWeight.w700)),
              ),
            ),
          if (_currentStep > 0) const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF09090B),
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 48),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              icon: _isSubmitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : Icon(
                      _currentStep == 2 ? Icons.check_circle_rounded : Icons.arrow_forward_rounded,
                      size: 18,
                    ),
              label: Text(
                _isSubmitting
                    ? 'Creating Outlet...'
                    : _currentStep == 2
                        ? 'Create Outlet Now'
                        : 'Next Step',
                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
              ),
              onPressed: _isSubmitting ? null : _nextStep,
            ),
          ),
        ],
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
          initialValue: value,
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
