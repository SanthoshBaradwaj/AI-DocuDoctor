import 'dart:io';
import 'package:dio/dio.dart';
import 'package:mime/mime.dart';
import '../config.dart';

class UploadService {
  final Dio _raw = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 30),
    sendTimeout: const Duration(minutes: 15),
    receiveTimeout: const Duration(minutes: 15),
  ));

  Future<void> uploadPresigned({
    required String presignUrl,
    required Map<String, dynamic> fields,
    required File file,
    void Function(int sent, int total)? onProgress,
  }) async {
    final mime = lookupMimeType(file.path) ?? 'application/octet-stream';

    // MinIO hostname fix for device: minio -> LAN
    String uploadUrl = presignUrl.replaceFirst(RegExp(r'^https?://minio:9000'), kStorageBase);

    // Build multipart form with all presign fields + file
    final fd = FormData();
    fields.forEach((k, v) => fd.fields.add(MapEntry(k, v.toString())));
    fd.files.add(MapEntry(
      'file',
      await MultipartFile.fromFile(
        file.path,
        filename: file.uri.pathSegments.last,
        contentType: DioMediaType.parse(mime),
      ),
    ));

    final res = await _raw.post(uploadUrl, data: fd, onSendProgress: onProgress, options: Options(
      contentType: 'multipart/form-data',
      followRedirects: true,
      validateStatus: (code) => code != null && code >= 200 && code < 500,
    ));

    if (res.statusCode == null || res.statusCode! >= 300) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        error: 'Upload failed with status ${res.statusCode}',
        type: DioExceptionType.badResponse,
      );
    }
  }
}
