import 'dart:io';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart'; // for MediaType.parse(...)
import '../config.dart';
import 'session.dart';

class ApiClient {
  final Dio _dio;
  ApiClient._(this._dio);

  factory ApiClient() {
    final dio = Dio(BaseOptions(
      baseUrl: kApiBase, // e.g. http://10.0.0.79:8000/api/v1
      connectTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(minutes: 5),
      receiveTimeout: const Duration(minutes: 5),
      headers: {HttpHeaders.contentTypeHeader: 'application/json'},
    ));

    dio.interceptors.add(InterceptorsWrapper(onRequest: (opt, handler) async {
      final token = await Session.token();
      if (token != null && token.isNotEmpty) {
        opt.headers[HttpHeaders.authorizationHeader] = 'Bearer $token';
      }
      handler.next(opt);
    }));

    return ApiClient._(dio);
  }

  Dio get dio => _dio;

  // -------- Docs --------
  Future<List<dynamic>> listDocs({
    String? domain,
    String? docType,
    String? status,
  }) async {
    final queryParams = <String, dynamic>{};
    if (domain != null) queryParams['domain'] = domain;
    if (docType != null) queryParams['doc_type'] = docType;
    if (status != null) queryParams['status'] = status;

    final res = await _dio.get('/docs', queryParameters: queryParams);
    if (res.data is List) return res.data as List;
    if (res.data is Map && res.data['value'] is List) {
      return (res.data['value'] as List);
    }
    return [];
  }

  Future<Map<String, dynamic>> getDocDetail(int id) async {
    final res = await _dio.get('/docs/$id');
    return Map<String, dynamic>.from(res.data);
  }

  /// Initialize upload - get presigned URL
  Future<Map<String, dynamic>> initUpload({
    required String filename,
    required String mimeType,
    required int sizeBytes,
    String? domain,
    String? docType,
  }) async {
    final res = await _dio.post('/docs/upload/presign', data: {
      'filename': filename,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      if (domain != null) 'domain': domain,
      if (docType != null) 'doc_type': docType,
    });
    return Map<String, dynamic>.from(res.data);
  }

  /// Notify backend that upload is complete
  Future<Map<String, dynamic>> notifyUploaded({
    required String storageKey,
    required String filename,
    required String mimeType,
    required int sizeBytes,
    String? domain,
    String? docType,
  }) async {
    final res = await _dio.post('/docs/notify', data: {
      'storage_key': storageKey,
      'filename': filename,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      if (domain != null) 'domain': domain,
      if (docType != null) 'doc_type': docType,
    });
    return Map<String, dynamic>.from(res.data);
  }

  Future<Map<String, dynamic>> getDownloadUrl(int id) async {
    final res = await _dio.get('/docs/$id/download');
    return Map<String, dynamic>.from(res.data);
  }

  // Legacy analyze endpoint (transitional)
  Future<Map<String, dynamic>> analyzeOne(int docId) async {
    final res = await _dio.post('/docs/analyze', data: {'docId': docId});
    return Map<String, dynamic>.from(res.data);
  }

  // -------- Chat --------
  /// Chat about a specific document
  Future<Map<String, dynamic>> chatWithDocument({
    required int docId,
    required List<Map<String, dynamic>> messages,
  }) async {
    final res = await _dio.post('/chat/document/$docId', data: {
      'messages': messages,
    });
    return Map<String, dynamic>.from(res.data);
  }

  /// Global chat across all documents
  Future<Map<String, dynamic>> chatGlobal({
    required List<Map<String, dynamic>> messages,
  }) async {
    final res = await _dio.post('/chat/global', data: {
      'messages': messages,
    });
    return Map<String, dynamic>.from(res.data);
  }

  // ========= Uploads =========

  /// Upload file to presigned URL
  Future<Response> uploadToPresigned({
    required String url,
    required Map<String, dynamic>? fields,
    required String filePath,
    required String fileName,
    String? contentType,
    void Function(int, int)? onSendProgress,
  }) async {
    final uri = Uri.parse(url);
    String uploadUrl = url;
    if (uri.host.toLowerCase() == 'minio' || uri.host == 'minio.local') {
      uploadUrl = Uri(
        scheme: uri.scheme,
        host: kDevHost, // e.g. 10.0.0.79
        port: uri.port,
        path: uri.path,
        query: uri.query,
      ).toString();
    }

    final form = FormData();
    if (fields != null) {
      fields.forEach((k, v) => form.fields.add(MapEntry(k, v.toString())));
    }
    form.files.add(MapEntry(
      'file',
      await MultipartFile.fromFile(
        filePath,
        filename: fileName,
        contentType: contentType != null ? MediaType.parse(contentType) : null,
      ),
    ));

    final miniDio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(minutes: 5),
      receiveTimeout: const Duration(minutes: 5),
    ));

    return miniDio.post(
      uploadUrl,
      data: form,
      onSendProgress: onSendProgress,
      options: Options(contentType: 'multipart/form-data'),
    );
  }

  // Legacy methods (kept for backward compatibility during transition)
  @Deprecated('Use initUpload and notifyUploaded instead')
  Future<Map<String, dynamic>> createPresign() async {
    // This is a fallback - should use initUpload instead
    final res = await _dio.post('/docs/upload/presign', data: {
      'filename': 'unknown',
      'mime_type': 'application/octet-stream',
      'size_bytes': 0,
    });
    return Map<String, dynamic>.from(res.data);
  }

  @Deprecated('Use notifyUploaded instead')
  Future<Map<String, dynamic>> notifyUploadedLegacy({
    required String key,
    required String filename,
    required int size,
    String? mime,
  }) async {
    return notifyUploaded(
      storageKey: key,
      filename: filename,
      mimeType: mime ?? 'application/octet-stream',
      sizeBytes: size,
    );
  }
}
