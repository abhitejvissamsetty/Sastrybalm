import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:sfa_mobile/services/api_client.dart';
import 'package:sfa_mobile/services/sync_service.dart';

void main() {
  late Directory directory;
  late HiveAesCipher cipher;
  late DateTime clock;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('safar-sync-test-');
    Hive.init(directory.path);
    cipher = HiveAesCipher(List<int>.generate(32, (index) => index));
    clock = DateTime(2026, 7, 29, 12);
  });

  tearDown(() async {
    await Hive.close();
    await directory.delete(recursive: true);
  });

  SyncService service({
    required SyncRequestSender sender,
    int maxAttempts = 5,
  }) =>
      SyncService(
        ApiClient(),
        cipher: cipher,
        hasConnection: () async => true,
        now: () => clock,
        requestSender: sender,
        maxAttempts: maxAttempts,
      );

  test('encrypted queue does not expose payload on disk', () async {
    final sync = service(sender: (_, __, ___, ____, _____) async => {});
    await sync.queueOperation(
      method: 'POST',
      path: '/payments',
      data: {'secretCustomerNote': 'plaintext-must-not-appear'},
    );
    await Hive.box('pending_ops').close();

    final bytes =
        await File('${directory.path}/pending_ops.hive').readAsBytes();
    final raw = String.fromCharCodes(bytes);
    expect(raw, isNot(contains('plaintext-must-not-appear')));
    expect(raw, isNot(contains('secretCustomerNote')));
  });

  test('preserves ordering, backs off, and reuses idempotency key', () async {
    final calls = <String>[];
    final keys = <String>[];
    var firstAttempt = true;
    final sync = service(sender: (method, path, query, data, key) async {
      calls.add(path);
      keys.add(key);
      if (path == '/first' && firstAttempt) {
        firstAttempt = false;
        throw DioException(requestOptions: RequestOptions(path: path));
      }
      return {'id': 1};
    });
    await sync.queueOperation(method: 'POST', path: '/first');
    await sync.queueOperation(method: 'POST', path: '/second');

    await sync.processPendingOps();
    expect(calls, ['/first']);
    expect(await sync.getPendingCount(), 2);
    await sync.processPendingOps();
    expect(calls, ['/first'], reason: 'backoff must suppress early retry');

    clock = clock.add(const Duration(seconds: 1));
    await sync.processPendingOps();
    expect(calls, ['/first', '/first', '/second']);
    expect(keys[0], keys[1]);
    expect(await sync.getPendingCount(), 0);
  });

  test('moves retry-exhausted operations to dead letter queue', () async {
    final sync = service(
      maxAttempts: 2,
      sender: (_, __, ___, ____, _____) async {
        throw StateError('offline failure');
      },
    );
    await sync.queueOperation(method: 'POST', path: '/fails');

    await sync.processPendingOps();
    clock = clock.add(const Duration(seconds: 1));
    await sync.processPendingOps();

    expect(await sync.getPendingCount(), 0);
    expect(await sync.getDeadLetterCount(), 1);
    final deadLetter = Hive.box('dead_letter_ops').values.single as Map;
    expect(deadLetter['failureReason'], 'retry_exhausted');
    expect(deadLetter['attemptCount'], 2);
  });

  test('dead-letters server conflicts without retrying', () async {
    final sync = service(sender: (_, path, __, ___, ____) async {
      throw DioException(
        requestOptions: RequestOptions(path: path),
        response: Response(
          requestOptions: RequestOptions(path: path),
          statusCode: 409,
        ),
      );
    });
    await sync.queueOperation(method: 'POST', path: '/conflict');
    await sync.processPendingOps();

    expect(await sync.getPendingCount(), 0);
    expect(await sync.getDeadLetterCount(), 1);
    final deadLetter = Hive.box('dead_letter_ops').values.single as Map;
    expect(deadLetter['failureReason'], 'conflict');
  });

  test('does not process queued work while connectivity is absent', () async {
    var called = false;
    final sync = SyncService(
      ApiClient(),
      cipher: cipher,
      hasConnection: () async => false,
      now: () => clock,
      requestSender: (_, __, ___, ____, _____) async {
        called = true;
        return {};
      },
    );
    await sync.queueOperation(method: 'POST', path: '/offline');
    await sync.processPendingOps();
    expect(called, isFalse);
    expect(await sync.getPendingCount(), 1);
  });
}
