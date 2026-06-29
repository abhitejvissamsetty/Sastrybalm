import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

class GpsStatusChip extends StatefulWidget {
  const GpsStatusChip({super.key});

  @override
  State<GpsStatusChip> createState() => _GpsStatusChipState();
}

class _GpsStatusChipState extends State<GpsStatusChip> {
  bool _checking = false;
  bool _hasGps = false;
  String _message = 'Checking GPS...';

  @override
  void initState() {
    super.initState();
    _checkGps();
  }

  Future<void> _checkGps() async {
    if (!mounted) return;
    setState(() {
      _checking = true;
    });

    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _hasGps = false;
          _message = 'GPS Disabled';
          _checking = false;
        });
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          setState(() {
            _hasGps = false;
            _message = 'No Permission';
            _checking = false;
          });
          return;
        }
      }
      if (permission == LocationPermission.deniedForever) {
        setState(() {
          _hasGps = false;
          _message = 'Blocked';
          _checking = false;
        });
        return;
      }

      setState(() {
        _hasGps = true;
        _message = 'GPS Connected';
        _checking = false;
      });
    } catch (_) {
      setState(() {
        _hasGps = false;
        _message = 'GPS Error';
        _checking = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    Color chipColor;
    IconData icon;

    if (_checking) {
      chipColor = Colors.amber.shade700;
      icon = Icons.location_searching_rounded;
    } else if (_hasGps) {
      chipColor = Colors.green.shade600;
      icon = Icons.gps_fixed_rounded;
    } else {
      chipColor = Colors.red.shade600;
      icon = Icons.gps_off_rounded;
    }

    return GestureDetector(
      onTap: _checkGps,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: chipColor.withOpacity(0.15),
          border: Border.all(color: chipColor.withOpacity(0.5)),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: chipColor, size: 14),
            const SizedBox(width: 4),
            Text(
              _message,
              style: TextStyle(
                color: chipColor,
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
