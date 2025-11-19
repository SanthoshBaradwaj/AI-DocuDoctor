import 'package:dio/dio.dart';
import '../core/logger.dart';

class WebhookService {
  final Dio _dio;
  WebhookService(this._dio);

  Future<Response<dynamic>> send({
    required String url,
    required Map<String, dynamic> payload,
    Map<String, String>? headers,
  }) async {
    final merged = {
      'X-App-Signature': 'demo-signature', // Replace with HMAC signing in prod
      if (headers != null) ...headers,
    };
    logI('Posting webhook to $url');
    return _dio.post(url, data: payload, options: Options(headers: merged));
  }
}
