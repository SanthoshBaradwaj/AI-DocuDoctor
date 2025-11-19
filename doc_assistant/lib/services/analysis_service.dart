import 'package:dio/dio.dart';
import '../core/config.dart';

class AnalysisService {
  final Dio _dio;
  AnalysisService(this._dio);

  /// Mock: POST /analyze with {docId}
  Future<Map<String, dynamic>> analyze(String docId) async {
    final res = await _dio.post('${AppConfig.apiBaseUrl}/analyze', data: {'docId': docId});
    return (res.data as Map<String, dynamic>? ??
        {'summary': 'Demo analysis summary for $docId', 'entities': []});
  }
}
