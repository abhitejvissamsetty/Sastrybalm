import 'package:dio/dio.dart';
import 'api_client.dart';

class ProcurementService {
  final ApiClient _client;
  ProcurementService(this._client);

  Future<List<dynamic>> materialRequests() async =>
      (await _client.dio.get('/procurement/material-requests')).data['items']
          as List<dynamic>;
  Future<List<dynamic>> workOrders() async =>
      (await _client.dio.get('/procurement/work-orders')).data['items']
          as List<dynamic>;
  Future<List<dynamic>> items() async =>
      (await _client.dio.get('/procurement/items')).data['items']
          as List<dynamic>;
  Future<List<dynamic>> assets() async =>
      (await _client.dio.get('/procurement/assets')).data['items']
          as List<dynamic>;
  Future<List<dynamic>> maintenanceLogs() async =>
      (await _client.dio.get('/procurement/maintenance-logs')).data['items']
          as List<dynamic>;

  Future<String> uploadImage(String path) async {
    final response = await _client.dio.post(
      '/procurement/attachments/upload',
      data: FormData.fromMap({'file': await MultipartFile.fromFile(path)}),
    );
    return response.data['file_url'] as String;
  }

  Future<void> submitRecce(int mrId, Map<String, dynamic> data) => _client.dio
      .post('/procurement/material-requests/$mrId/recce', data: data);
  Future<void> submitQuotation(Map<String, dynamic> data) =>
      _client.dio.post('/procurement/quotations', data: data);
  Future<void> acknowledge(int workOrderId) =>
      _client.dio.post('/procurement/work-orders/$workOrderId/acknowledge');
  Future<void> reportWorkOrderProgress(
          int workOrderId, int progress, String remarks) =>
      _client.dio.post('/procurement/work-orders/$workOrderId/progress',
          data: {'progress_percent': progress, 'remarks': remarks});
  Future<void> completeQc(int workOrderId, Map<String, dynamic> data) => _client
      .dio
      .post('/procurement/work-orders/$workOrderId/qc-complete', data: data);
  Future<void> recallQc(int workOrderId, String reason) =>
      _client.dio.post('/procurement/work-orders/$workOrderId/recall-qc',
          data: {'reason': reason});
  Future<void> deployItem(int itemId, String description, String imageUrl) =>
      _client.dio.post('/procurement/items/$itemId/create-asset',
          data: {'notes': description, 'image_url': imageUrl});
  Future<void> createMaintenance(
          int assetId, String issue, List<String> images) =>
      _client.dio.post('/procurement/assets/$assetId/maintenance-logs',
          data: {'notes': issue, 'image_urls': images});
  Future<void> reportMaintenance(int logId, int progress, String remarks,
          {List<String> imageUrls = const []}) =>
      _client.dio.post('/procurement/maintenance-logs/$logId/progress', data: {
        'progress_percent': progress,
        'remarks': remarks,
        'image_urls': imageUrls
      });
  Future<void> validateMaintenance(int logId) =>
      _client.dio.post('/procurement/maintenance-logs/$logId/validate');
}
