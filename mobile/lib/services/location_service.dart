import 'package:geolocator/geolocator.dart';

enum LocationFailureCode {
  serviceDisabled,
  permissionDenied,
  permissionDeniedForever,
  unavailable,
  spoofed,
  stale,
  inaccurate,
  invalidCoordinates,
}

class LocationFailure implements Exception {
  final LocationFailureCode code;
  final String message;

  const LocationFailure(this.code, this.message);

  @override
  String toString() => message;
}

abstract class LocationGateway {
  Future<bool> isServiceEnabled();
  Future<LocationPermission> checkPermission();
  Future<LocationPermission> requestPermission();
  Future<Position> currentPosition();
}

class GeolocatorLocationGateway implements LocationGateway {
  @override
  Future<bool> isServiceEnabled() => Geolocator.isLocationServiceEnabled();

  @override
  Future<LocationPermission> checkPermission() => Geolocator.checkPermission();

  @override
  Future<LocationPermission> requestPermission() =>
      Geolocator.requestPermission();

  @override
  Future<Position> currentPosition() => Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );
}

class LocationService {
  final LocationGateway gateway;
  final Duration maximumAge;
  final double maximumAccuracyMetres;
  final DateTime Function() now;

  LocationService({
    LocationGateway? gateway,
    this.maximumAge = const Duration(minutes: 2),
    this.maximumAccuracyMetres = 100,
    DateTime Function()? now,
  })  : gateway = gateway ?? GeolocatorLocationGateway(),
        now = now ?? DateTime.now;

  Future<Position> verifiedCurrentPosition() async {
    if (!await gateway.isServiceEnabled()) {
      throw const LocationFailure(
        LocationFailureCode.serviceDisabled,
        'Location services are disabled.',
      );
    }

    var permission = await gateway.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await gateway.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      throw const LocationFailure(
        LocationFailureCode.permissionDeniedForever,
        'Location permission is permanently denied.',
      );
    }
    if (permission == LocationPermission.denied) {
      throw const LocationFailure(
        LocationFailureCode.permissionDenied,
        'Location permission was denied.',
      );
    }

    Position position;
    try {
      position = await gateway.currentPosition();
    } catch (_) {
      throw const LocationFailure(
        LocationFailureCode.unavailable,
        'A current GPS position is unavailable.',
      );
    }
    validate(position);
    return position;
  }

  void validate(Position position) {
    if (position.latitude < -90 ||
        position.latitude > 90 ||
        position.longitude < -180 ||
        position.longitude > 180) {
      throw const LocationFailure(
        LocationFailureCode.invalidCoordinates,
        'GPS returned invalid coordinates.',
      );
    }
    if (position.isMocked) {
      throw const LocationFailure(
        LocationFailureCode.spoofed,
        'Mocked GPS locations are not accepted.',
      );
    }
    if (now().difference(position.timestamp).abs() > maximumAge) {
      throw const LocationFailure(
        LocationFailureCode.stale,
        'The GPS position is stale.',
      );
    }
    if (!position.accuracy.isFinite ||
        position.accuracy < 0 ||
        position.accuracy > maximumAccuracyMetres) {
      throw const LocationFailure(
        LocationFailureCode.inaccurate,
        'GPS accuracy is insufficient.',
      );
    }
  }
}
