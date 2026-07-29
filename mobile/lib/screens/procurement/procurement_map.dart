import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class ProcurementMap extends StatelessWidget {
  final List<dynamic> records;
  const ProcurementMap({super.key, required this.records});

  @override
  Widget build(BuildContext context) {
    final points = records
        .map((raw) {
          final record = raw as Map<String, dynamic>;
          final outlet = record['outlet'] as Map<String, dynamic>?;
          final lat = (outlet?['gps_lat'] as num?)?.toDouble();
          final lng = (outlet?['gps_lng'] as num?)?.toDouble();
          return lat == null || lng == null
              ? null
              : (record, outlet!, LatLng(lat, lng));
        })
        .whereType<(Map<String, dynamic>, Map<String, dynamic>, LatLng)>()
        .toList();
    if (points.isEmpty) {
      return const Center(child: Text('No mapped Outlet locations.'));
    }
    return FlutterMap(
      options: MapOptions(initialCenter: points.first.$3, initialZoom: 11),
      children: [
        TileLayer(
            urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'com.safar.sfa'),
        MarkerLayer(
            markers: points
                .map((point) => Marker(
                      point: point.$3,
                      width: 130,
                      height: 55,
                      child: Column(children: [
                        const Icon(Icons.location_pin,
                            color: Color(0xFF09090B), size: 32),
                        Container(
                            color: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 4),
                            child: Text(point.$2['name'] ?? 'Outlet',
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold))),
                      ]),
                    ))
                .toList()),
      ],
    );
  }
}
