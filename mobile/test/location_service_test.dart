import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:sfa_mobile/services/location_service.dart';
import 'package:sfa_mobile/utils/haversine.dart';

class FakeLocationGateway implements LocationGateway {
  bool enabled = true;
  LocationPermission permission = LocationPermission.always;
  LocationPermission requestedPermission = LocationPermission.always;
  Position? position;
  Object? positionError;

  @override
  Future<LocationPermission> checkPermission() async => permission;

  @override
  Future<Position> currentPosition() async {
    if (positionError != null) throw positionError!;
    return position!;
  }

  @override
  Future<bool> isServiceEnabled() async => enabled;

  @override
  Future<LocationPermission> requestPermission() async => requestedPermission;
}

Position samplePosition(
  DateTime timestamp, {
  bool isMocked = false,
  double accuracy = 5,
}) =>
    Position(
      latitude: 17.385,
      longitude: 78.4867,
      timestamp: timestamp,
      accuracy: accuracy,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
      isMocked: isMocked,
    );

void main() {
  final now = DateTime(2026, 7, 29, 12);

  test('accepts a fresh accurate real position', () async {
    final gateway = FakeLocationGateway()
      ..position = samplePosition(now.subtract(const Duration(seconds: 10)));
    final result = await LocationService(gateway: gateway, now: () => now)
        .verifiedCurrentPosition();
    expect(result.latitude, 17.385);
  });

  test('fails when GPS service is unavailable', () async {
    final gateway = FakeLocationGateway()..enabled = false;
    expect(
      () => LocationService(gateway: gateway).verifiedCurrentPosition(),
      throwsA(
        isA<LocationFailure>().having(
          (e) => e.code,
          'code',
          LocationFailureCode.serviceDisabled,
        ),
      ),
    );
  });

  test('fails for denied and permanently denied permission', () async {
    for (final denied in [
      LocationPermission.denied,
      LocationPermission.deniedForever,
    ]) {
      final gateway = FakeLocationGateway()
        ..permission = LocationPermission.denied
        ..requestedPermission = denied;
      expect(
        () => LocationService(gateway: gateway).verifiedCurrentPosition(),
        throwsA(isA<LocationFailure>()),
      );
    }
  });

  test('fails when provider cannot obtain a position', () async {
    final gateway = FakeLocationGateway()..positionError = Exception('timeout');
    expect(
      () => LocationService(gateway: gateway).verifiedCurrentPosition(),
      throwsA(
        isA<LocationFailure>().having(
          (e) => e.code,
          'code',
          LocationFailureCode.unavailable,
        ),
      ),
    );
  });

  test('rejects mocked, stale, and inaccurate positions', () async {
    final cases = <Position, LocationFailureCode>{
      samplePosition(now, isMocked: true): LocationFailureCode.spoofed,
      samplePosition(now.subtract(const Duration(minutes: 3))):
          LocationFailureCode.stale,
      samplePosition(now, accuracy: 150): LocationFailureCode.inaccurate,
    };
    for (final entry in cases.entries) {
      final gateway = FakeLocationGateway()..position = entry.key;
      expect(
        () => LocationService(gateway: gateway, now: () => now)
            .verifiedCurrentPosition(),
        throwsA(
          isA<LocationFailure>().having(
            (e) => e.code,
            'code',
            entry.value,
          ),
        ),
      );
    }
  });

  test('classifies positions outside the configured outlet radius', () {
    final near = Haversine.distance(17.385, 78.4867, 17.3851, 78.4868);
    final far = Haversine.distance(17.385, 78.4867, 17.395, 78.4967);
    expect(near, lessThanOrEqualTo(100));
    expect(far, greaterThan(100));
  });
}
