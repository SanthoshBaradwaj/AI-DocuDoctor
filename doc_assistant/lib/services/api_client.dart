import 'dart:io';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';
import '../config.dart';
import '../models/doc.dart';
import '../models/chat.dart';
import 'session.dart';

class ApiClient {
  final Dio _dio;
  ApiClient._(this._dio);

  factory ApiClient() {
    final dio = Dio(BaseOptions(
      baseUrl: kApiBase, // Uses kApiBase getter (web vs mobile)
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
  Future<List<Doc>> fetchDocs({
    String? domain,
    String? docType,
    String? status,
  }) async {
    final queryParams = <String, dynamic>{};
    if (domain != null) queryParams['domain'] = domain;
    if (docType != null) queryParams['doc_type'] = docType;
    if (status != null) queryParams['status'] = status;

    final res = await _dio.get('/docs', queryParameters: queryParams);
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

  Future<DocDetail> fetchDocDetail(int id) async {
    final res = await _dio.get('/docs/$id');
    return DocDetail.fromJson(res.data as Map<String, dynamic>);
  }

  /// Initialize upload - get presigned URL
  Future<UploadInitOut> initUpload(UploadInitIn req) async {
    final res = await _dio.post('/docs/upload/presign', data: {
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
    final res = await _dio.post('/docs/notify', data: {
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
  Future<ChatResponse> chatWithDocument(
      int docId, List<ChatMessage> messages) async {
    final res = await _dio.post('/chat/document/$docId', data: {
      'messages': messages.map((m) => m.toJson()).toList(),
    });
    return ChatResponse.fromJson(res.data as Map<String, dynamic>);
  }

  /// Global chat across all documents
  Future<ChatResponse> chatGlobal(List<ChatMessage> messages) async {
    final res = await _dio.post('/chat/global', data: {
      'messages': messages.map((m) => m.toJson()).toList(),
    });
    return ChatResponse.fromJson(res.data as Map<String, dynamic>);
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
    // For web, we need to handle MinIO URLs differently
    if (uri.host.toLowerCase() == 'minio' || uri.host == 'minio.local') {
      uploadUrl = Uri(
        scheme: uri.scheme,
        host: 'localhost', // For web, use localhost
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
  Future<Map<String, dynamic>> getDocDetail(int id) async {
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
