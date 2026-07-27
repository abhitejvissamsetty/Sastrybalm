class Outlet {
  final int id;
  final String name;
  final String code;
  final int? beatId;
  final int? territoryId;
  final String? ownerName;
  final String? mobile;
  final String? address;
  final String? channel;
  final double? gpsLat;
  final double? gpsLng;
  final String? photoUrl;
  final bool isIncomplete;
  final List<String> missingFields;

  Outlet({
    required this.id,
    required this.name,
    required this.code,
    this.beatId,
    this.territoryId,
    this.ownerName,
    this.mobile,
    this.address,
    this.channel,
    this.gpsLat,
    this.gpsLng,
    this.photoUrl,
    this.isIncomplete = false,
    this.missingFields = const [],
  });

  factory Outlet.fromJson(Map<String, dynamic> json) => Outlet(
    id: json['id'],
    name: json['name'] ?? '',
    code: json['code'] ?? '',
    beatId: json['beat_id'],
    territoryId: json['territory_id'],
    ownerName: json['owner_name'],
    mobile: json['mobile'],
    address: json['address'],
    channel: json['channel'],
    gpsLat: (json['gps_lat'] as num?)?.toDouble(),
    gpsLng: (json['gps_lng'] as num?)?.toDouble(),
    photoUrl: json['photo_url'],
    isIncomplete: json['is_incomplete'] == true,
    missingFields: json['missing_fields'] != null ? List<String>.from(json['missing_fields']) : [],
  );

  bool get hasGps => gpsLat != null && gpsLng != null;

  String get channelLabel {
    switch (channel) {
      case 'general_trade': return 'GT';
      case 'modern_trade': return 'MT';
      case 'pharmacy': return 'Pharmacy';
      case 'horeca': return 'HoReCa';
      case 'institutional': return 'Institutional';
      default: return channel ?? 'General';
    }
  }
}

class Beat {
  final int id;
  final String name;
  final String code;
  final String beatType;
  final String? l1PositionName;
  final String? assignedUserName;
  final int activeOutletCount;
  final List<Outlet> outlets;

  Beat({
    required this.id,
    required this.name,
    required this.code,
    required this.beatType,
    this.l1PositionName,
    this.assignedUserName,
    this.activeOutletCount = 0,
    required this.outlets,
  });

  factory Beat.fromJson(Map<String, dynamic> json) => Beat(
    id: json['id'],
    name: json['name'] ?? '',
    code: json['code'] ?? '',
    beatType: json['beat_type'] ?? 'GT',
    l1PositionName: json['l1_position_name'],
    assignedUserName: json['assigned_user_name'],
    activeOutletCount: json['active_outlet_count'] ?? 0,
    outlets: [],
  );
}
