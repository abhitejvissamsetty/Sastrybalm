import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:sfa_mobile/services/image_picker_service.dart';
import 'package:sfa_mobile/services/retry_policy.dart';

class FakePicker implements ImagePickerGateway {
  XFile? result;
  Object? error;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
  }) async {
    if (error != null) throw error!;
    return result;
  }
}

void main() {
  late Directory directory;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('safar-image-test-');
  });

  tearDown(() async {
    await directory.delete(recursive: true);
  });

  Future<XFile> image(String name, List<int> bytes) async {
    final file = File('${directory.path}/$name');
    await file.writeAsBytes(bytes);
    return XFile(file.path);
  }

  test('camera and gallery denial return no fabricated image', () async {
    final picker = FakePicker()..error = Exception('permission denied');
    final service = ImagePickerService(picker: picker);
    expect(await service.captureFromCamera(), isNull);
    expect(await service.pickFromGallery(), isNull);
  });

  test('rejects invalid, empty, and oversized images', () async {
    final picker = FakePicker();
    final service = ImagePickerService(picker: picker, maximumBytes: 4);

    picker.result = await image('payload.exe', [1]);
    expect(await service.pickFromGallery(), isNull);
    picker.result = await image('empty.jpg', []);
    expect(await service.pickFromGallery(), isNull);
    picker.result = await image('large.png', [1, 2, 3, 4, 5]);
    expect(await service.pickFromGallery(), isNull);
  });

  test('a replacement selection supersedes the previous valid image', () async {
    final picker = FakePicker();
    final service = ImagePickerService(picker: picker);
    picker.result = await image('original.jpg', [1]);
    var selected = await service.pickFromGallery();
    picker.result = await image('replacement.jpg', [2]);
    selected = await service.pickFromGallery();
    expect(selected?.name, 'replacement.jpg');
  });

  test('transient upload failure retries with exponential backoff', () async {
    var attempts = 0;
    final delays = <Duration>[];
    final policy = RetryPolicy(
      maximumAttempts: 3,
      initialDelay: const Duration(milliseconds: 10),
      delay: (duration) async => delays.add(duration),
    );
    final result = await policy.execute(
      () async {
        attempts++;
        if (attempts < 3) throw StateError('temporary upload failure');
        return 'uploaded';
      },
      shouldRetry: (_) => true,
    );
    expect(result, 'uploaded');
    expect(attempts, 3);
    expect(delays, [
      const Duration(milliseconds: 10),
      const Duration(milliseconds: 20),
    ]);
  });

  test('permanent upload failure is not retried', () async {
    var attempts = 0;
    final policy = RetryPolicy(delay: (_) async {});
    await expectLater(
      policy.execute(
        () async {
          attempts++;
          throw ArgumentError('invalid image');
        },
        shouldRetry: (_) => false,
      ),
      throwsArgumentError,
    );
    expect(attempts, 1);
  });
}
