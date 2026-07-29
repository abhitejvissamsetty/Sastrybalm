import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';
import '../../services/operations_service.dart';

class EisMisScreen extends ConsumerStatefulWidget {
  const EisMisScreen({super.key});

  @override
  ConsumerState<EisMisScreen> createState() => _EisMisScreenState();
}

class _EisMisScreenState extends ConsumerState<EisMisScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  Map<String, dynamic>? _eisData;
  Map<String, dynamic>? _misData;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    try {
      final client = ref.read(apiClientProvider);
      final service = AnalyticsService(client);
      final eis = await service.getEis();
      Map<String, dynamic>? mis;
      try {
        mis = await service.getMis();
      } catch (_) {}

      if (mounted) {
        setState(() {
          _eisData = eis;
          _misData = mis;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('Performance & Analytics'),
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF09090B),
          unselectedLabelColor: const Color(0xFF71717A),
          indicatorColor: const Color(0xFF09090B),
          tabs: const [
            Tab(text: 'EIS (Self)'),
            Tab(text: 'MIS (Managerial)'),
          ],
        ),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF09090B)))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildEisView(),
                _buildMisView(),
              ],
            ),
    );
  }

  Widget _buildEisView() {
    if (_eisData == null) {
      return const Center(child: Text('No EIS data available.'));
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Employee Information System',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.3,
            children: [
              _buildStatCard(
                  'Secondary Orders',
                  '${_eisData!['secondary_orders_count']}',
                  Icons.receipt_long_outlined),
              _buildStatCard(
                  'Primary Orders',
                  '${_eisData!['primary_orders_count']}',
                  Icons.shopping_bag_outlined),
              _buildStatCard('Payments', '${_eisData!['payments_count']}',
                  Icons.payments_outlined),
              _buildStatCard(
                  'Material Requests',
                  '${_eisData!['material_requests_count']}',
                  Icons.inventory_2_outlined),
              _buildStatCard(
                  'Attendance Days',
                  '${_eisData!['attendance_days_count']} Days',
                  Icons.calendar_today_outlined),
              _buildStatCard(
                  'Productivity KPI',
                  '${_eisData!['productivity_kpi']}',
                  Icons.trending_up_rounded),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMisView() {
    if (_misData == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text(
              'MIS Analytics are restricted to Territory Managers & Regional Leaders.'),
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Managerial Information System (Team)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.3,
            children: [
              _buildStatCard(
                  'Team Primary Orders',
                  '${_misData!['team_primary_orders']}',
                  Icons.shopping_bag_rounded),
              _buildStatCard(
                  'Team Secondary Orders',
                  '${_misData!['team_secondary_orders']}',
                  Icons.receipt_rounded),
              _buildStatCard(
                  'Payments Collected',
                  '${_misData!['team_payments_collected']}',
                  Icons.payments_rounded),
              _buildStatCard(
                  'Material Requests',
                  '${_misData!['team_material_requests']}',
                  Icons.inventory_rounded),
              _buildStatCard(
                  'Outlets Managed',
                  '${_misData!['total_outlets_managed']}',
                  Icons.storefront_rounded),
              _buildStatCard(
                  'Team KPI Rating',
                  '${_misData!['team_productivity_kpi']}',
                  Icons.leaderboard_rounded),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE4E4E7)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: const Color(0xFF09090B), size: 20),
          const SizedBox(height: 8),
          Text(value,
              style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF09090B))),
          const SizedBox(height: 2),
          Text(title,
              style: const TextStyle(fontSize: 11, color: Color(0xFF71717A))),
        ],
      ),
    );
  }
}
