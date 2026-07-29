import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

abstract class ImagePickerGateway {
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
  });
}

class PlatformImagePickerGateway implements ImagePickerGateway {
  final ImagePicker picker;

  PlatformImagePickerGateway([ImagePicker? picker])
      : picker = picker ?? ImagePicker();

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
  }) =>
      picker.pickImage(
        source: source,
        maxWidth: maxWidth,
        maxHeight: maxHeight,
        imageQuality: imageQuality,
      );
}

class ImagePickerService {
  final ImagePickerGateway _picker;
  final int maximumBytes;

  ImagePickerService({
    ImagePickerGateway? picker,
    this.maximumBytes = 5 * 1024 * 1024,
  }) : _picker = picker ?? PlatformImagePickerGateway();

  Future<XFile?> captureFromCamera(
      {double? maxWidth, double? maxHeight, int? imageQuality}) async {
    try {
      final file = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: maxWidth ?? 1280,
        maxHeight: maxHeight ?? 1280,
        imageQuality: imageQuality ?? 85,
      );
      return await _validated(file);
    } catch (e) {
      debugPrint('Camera pick error: $e');
      return null;
    }
  }

  Future<XFile?> pickFromGallery(
      {double? maxWidth, double? maxHeight, int? imageQuality}) async {
    try {
      final file = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: maxWidth ?? 1280,
        maxHeight: maxHeight ?? 1280,
        imageQuality: imageQuality ?? 85,
      );
      return await _validated(file);
    } catch (e) {
      debugPrint('Gallery pick error: $e');
      return null;
    }
  }

  Future<XFile?> _validated(XFile? file) async {
    if (file == null) return null;
    final extension = file.name.split('.').last.toLowerCase();
    if (!const {'jpg', 'jpeg', 'png', 'webp'}.contains(extension)) {
      throw const FormatException('Unsupported image format.');
    }
    final length = await file.length();
    if (length <= 0 || length > maximumBytes) {
      throw const FormatException('Image is empty or exceeds the size limit.');
    }
    return file;
  }

  Future<XFile?> showImageSourceDialog(BuildContext context) async {
    return showModalBottomSheet<XFile?>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: const Color(0xFFE4E4E7),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Upload Photo',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF09090B)),
            ),
            const SizedBox(height: 14),
            ListTile(
              leading: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.camera_alt_rounded,
                    color: Color(0xFF09090B)),
              ),
              title: const Text('Take Photo with Camera',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              subtitle: const Text(
                  'Capture photo directly from your device camera',
                  style: TextStyle(fontSize: 12, color: Color(0xFF71717A))),
              onTap: () async {
                final file = await captureFromCamera();
                if (ctx.mounted) Navigator.pop(ctx, file);
              },
            ),
            const SizedBox(height: 8),
            ListTile(
              leading: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF4F4F5),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.photo_library_rounded,
                    color: Color(0xFF09090B)),
              ),
              title: const Text('Choose from Gallery',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              subtitle: const Text(
                  'Select an existing photo from device storage',
                  style: TextStyle(fontSize: 12, color: Color(0xFF71717A))),
              onTap: () async {
                final file = await pickFromGallery();
                if (ctx.mounted) Navigator.pop(ctx, file);
              },
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}
