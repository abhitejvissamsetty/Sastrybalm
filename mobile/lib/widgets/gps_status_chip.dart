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
      chipColor = const Color(0xFFFBBF24); // Amber 400
      icon = Icons.location_searching_rounded;
    } else if (_hasGps) {
      chipColor = const Color(0xFF34D399); // Emerald 400
      icon = Icons.gps_fixed_rounded;
    } else {
      chipColor = const Color(0xFFF87171); // Rose 400
      icon = Icons.gps_off_rounded;
    }

    return GestureDetector(
      onTap: _checkGps,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.18),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.white.withOpacity(0.25), width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: chipColor, size: 13),
            const SizedBox(width: 5),
            Text(
              _message,
              style: TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
