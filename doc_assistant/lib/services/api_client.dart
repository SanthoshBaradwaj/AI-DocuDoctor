import 'dart:io';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';
import 'package:flutter/foundation.dart';
import '../config.dart';
import '../models/doc.dart';
import '../models/chat.dart';
import '../models/api_error.dart';
import '../models/doc_status.dart';
import 'session.dart';

class ApiClient {
  final Dio _dio;
  ApiClient._(this._dio);

  factory ApiClient() {
    final baseUrl = kApiBase;
    // Debug: Print baseUrl for troubleshooting
    debugPrint('ApiClient baseUrl: $baseUrl');
    
    final dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(minutes: 5),
      receiveTimeout: const Duration(minutes: 5),
      headers: {HttpHeaders.contentTypeHeader: 'application/json'},
    ));

    // Request interceptor: Add auth token and optional request_id
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (opt, handler) async {
        final token = await Session.token();
        if (token != null && token.isNotEmpty) {
          opt.headers[HttpHeaders.authorizationHeader] = 'Bearer $token';
        }
        
        // Add X-Request-Id header if not already present
        final requestId = const Uuid().v4();
        if (!opt.headers.containsKey('X-Request-Id')) {
          opt.headers['X-Request-Id'] = requestId;
        }
        
        // Debug: Print full URL for troubleshooting
        final fullUrl = '${opt.baseUrl}${opt.path}';
        debugPrint('ApiClient request: ${opt.method} $fullUrl [request_id: $requestId]');
        
        handler.next(opt);
      },
      onError: (error, handler) {
        // Parse normalized error envelope from backend
        if (error.response != null) {
          try {
            final data = error.response!.data;
            if (data is Map<String, dynamic> && data.containsKey('error_code')) {
              final apiError = ApiError.fromJson(data);
              error = DioException(
                requestOptions: error.requestOptions,
                response: error.response,
                error: apiError,
                type: DioExceptionType.badResponse,
              );
            }
          } catch (e) {
            // If parsing fails, continue with original error
          }
        }
        handler.next(error);
      },
    ));

    return ApiClient._(dio);
  }

  Dio get dio => _dio;

  // -------- Docs --------
  Future<List<Doc>> fetchDocs({
    String? domain,
    String? docType,
    String? status,
  }) async {
    final queryParams = <String, dynamic>{};
    if (domain != null) queryParams['domain'] = domain;
    if (docType != null) queryParams['doc_type'] = docType;
    if (status != null) queryParams['status'] = status;

    final res = await _dio.get('/api/v1/docs', queryParameters: queryParams);
    if (res.data is List) {
      return (res.data as List)
          .map((item) => Doc.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    if (res.data is Map && res.data['value'] is List) {
      return (res.data['value'] as List)
          .map((item) => Doc.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  Future<DocDetail> fetchDocDetail(String id) async {
    final res = await _dio.get('/api/v1/docs/$id');
    return DocDetail.fromJson(res.data as Map<String, dynamic>);
  }

  /// Get document status (for polling)
  Future<DocStatus> fetchDocStatus(String id) async {
    final res = await _dio.get('/api/v1/docs/$id/status');
    return DocStatus.fromJson(res.data as Map<String, dynamic>);
  }

  /// Initialize upload - get presigned URL
  Future<UploadInitOut> initUpload(UploadInitIn req) async {
    final res = await _dio.post('/api/v1/docs/upload/presign', data: {
      'filename': req.filename,
      'mime_type': req.mimeType,
      'size_bytes': req.sizeBytes,
      if (req.domain != null) 'domain': req.domain,
      if (req.docType != null) 'doc_type': req.docType,
    });
    return UploadInitOut.fromJson(res.data as Map<String, dynamic>);
  }

  /// Notify backend that upload is complete
  Future<DocDetail> notifyUploaded(UploadNotifyIn req) async {
    final res = await _dio.post('/api/v1/docs/notify', data: {
      'storage_key': req.storageKey,
      'filename': req.filename,
      'mime_type': req.mimeType,
      'size_bytes': req.sizeBytes,
      if (req.domain != null) 'domain': req.domain,
      if (req.docType != null) 'doc_type': req.docType,
    });
    return DocDetail.fromJson(res.data as Map<String, dynamic>);
  }

  /// Chat about a specific document
  /// Returns ChatResponse or throws ApiError
  Future<ChatResponse> chatWithDocument(
      String docId, List<ChatMessage> messages, {String? requestId}) async {
    final options = Options();
    if (requestId != null) {
      options.headers = {'X-Request-Id': requestId};
    }
    
    try {
      final res = await _dio.post(
        '/api/v1/chat/document/$docId',
        data: {
          'messages': messages.map((m) => m.toJson()).toList(),
        },
        options: options,
      );
      return ChatResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      if (e.error is ApiError) {
        throw e.error as ApiError;
      }
      // Re-throw as ApiError if we can parse it
      if (e.response != null) {
        final data = e.response!.data;
        if (data is Map<String, dynamic> && data.containsKey('error_code')) {
          throw ApiError.fromJson(data);
        }
      }
      // Fallback to generic error
      throw ApiError(
        errorCode: 'NETWORK_ERROR',
        message: e.message ?? 'Network error occurred',
        requestId: requestId,
      );
    }
  }

  /// Global chat across all documents
  /// Returns ChatResponse or throws ApiError
  Future<ChatResponse> chatGlobal(List<ChatMessage> messages, {String? requestId}) async {
    try {
      final options = Options();
      if (requestId != null) {
        options.headers = {'X-Request-Id': requestId};
      }
      
      final res = await _dio.post(
        '/api/v1/chat/global',
        data: {
          'messages': messages.map((m) => m.toJson()).toList(),
        },
        options: options,
      );
      return ChatResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      if (e.error is ApiError) {
        throw e.error as ApiError;
      }
      // Re-throw as ApiError if we can parse it
      if (e.response != null) {
        final data = e.response!.data;
        if (data is Map<String, dynamic> && data.containsKey('error_code')) {
          throw ApiError.fromJson(data);
        }
      }
      // Fallback to generic error
      throw ApiError(
        errorCode: 'NETWORK_ERROR',
        message: e.message ?? 'Network error occurred',
        requestId: requestId,
      );
    }
  }

  // ========= Uploads =========

  /// Upload file to presigned URL (GCS signed URL)
  /// For GCS: HTTP PUT with raw bytes and Content-Type header
  /// For MinIO (local dev): HTTP PUT with raw bytes
  Future<Response> uploadToPresigned({
    required String url,
    required String filePath,
    required String fileName,
    String? contentType,
    void Function(int, int)? onSendProgress,
  }) async {
    final uri = Uri.parse(url);
    String uploadUrl = url;
    
    // For web, handle MinIO URLs differently
    if (kIsWeb && (uri.host.toLowerCase() == 'minio' || uri.host == 'minio.local')) {
      uploadUrl = Uri(
        scheme: uri.scheme,
        host: 'localhost',
        port: uri.port,
        path: uri.path,
        query: uri.query,
      ).toString();
    }

    final file = File(filePath);
    final bytes = await file.readAsBytes();

    final miniDio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(minutes: 5),
      receiveTimeout: const Duration(minutes: 5),
    ));

    // GCS signed URLs require HTTP PUT with raw bytes
    return miniDio.put(
      uploadUrl,
      data: bytes,
      onSendProgress: onSendProgress,
      options: Options(
        contentType: contentType ?? 'application/octet-stream',
        headers: {
          if (contentType != null) 'Content-Type': contentType,
        },
      ),
    );
  }

  /// Upload bytes to presigned URL (for web)
  /// GCS signed URLs require HTTP PUT with raw bytes
  Future<Response> uploadBytesToPresigned({
    required String url,
    required List<int> bytes,
    String? contentType,
    void Function(int, int)? onSendProgress,
  }) async {
    final uri = Uri.parse(url);
    String uploadUrl = url;
    
    // For web, handle MinIO URLs differently
    if (kIsWeb && (uri.host.toLowerCase() == 'minio' || uri.host == 'minio.local')) {
      uploadUrl = Uri(
        scheme: uri.scheme,
        host: 'localhost',
        port: uri.port,
        path: uri.path,
        query: uri.query,
      ).toString();
    }

    final miniDio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(minutes: 5),
      receiveTimeout: const Duration(minutes: 5),
    ));

    // GCS signed URLs require HTTP PUT with raw bytes
    return miniDio.put(
      uploadUrl,
      data: bytes,
      onSendProgress: onSendProgress,
      options: Options(
        contentType: contentType ?? 'application/octet-stream',
        headers: {
          if (contentType != null) 'Content-Type': contentType,
        },
      ),
    );
  }

  // Legacy methods - deprecated
  @Deprecated('Use fetchDocs instead')
  Future<List<dynamic>> listDocs({
    String? domain,
    String? docType,
    String? status,
  }) async {
    return fetchDocs(domain: domain, docType: docType, status: status)
        .then((docs) => docs.map((d) => d.toJson()).toList());
  }

  @Deprecated('Use fetchDocDetail instead')
  Future<Map<String, dynamic>> getDocDetail(String id) async {
    return fetchDocDetail(id).then((doc) => doc.toJson());
  }
}

// Request/Response models for upload
class UploadInitIn {
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final String? domain;
  final String? docType;

  UploadInitIn({
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    this.domain,
    this.docType,
  });
}

class UploadInitOut {
  final String storageKey;
  final String uploadUrl;
  final Map<String, dynamic>? uploadFields;
  final int maxSizeBytes;

  UploadInitOut({
    required this.storageKey,
    required this.uploadUrl,
    this.uploadFields,
    required this.maxSizeBytes,
  });

  factory UploadInitOut.fromJson(Map<String, dynamic> json) {
    return UploadInitOut(
      storageKey: json['storage_key'] as String,
      uploadUrl: json['upload_url'] as String,
      uploadFields: json['upload_fields'] as Map<String, dynamic>?,
      maxSizeBytes: json['max_size_bytes'] as int,
    );
  }
}

class UploadNotifyIn {
  final String storageKey;
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final String? domain;
  final String? docType;

  UploadNotifyIn({
    required this.storageKey,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    this.domain,
    this.docType,
  });
}
