import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../services/api_client.dart';

class UploadPage extends StatefulWidget {
  const UploadPage({super.key});

  @override
  State<UploadPage> createState() => _UploadPageState();
}

class _UploadPageState extends State<UploadPage> {
  double _progress = 0.0;
  bool _busy = false;
  String? _lastStatus;

  Future<void> _pickAndUpload() async {
    setState(() {
      _progress = 0.0;
      _busy = true;
      _lastStatus = null;
    });

    try {
      final picked = await FilePicker.platform.pickFiles(
        withReadStream: true,
        type: FileType.custom,
        allowedExtensions: [
          'txt',
          'pdf',
          'doc',
          'docx',
          'xlsx',
          'jpg',
          'jpeg',
          'png'
        ],
      );
      if (picked == null) {
        setState(() => _busy = false);
        return;
      }
      final f = picked.files.first;
      if (f.path == null) throw 'File path is null';

      final api = ApiClient();
      final file = File(f.path!);
      final fileSize = await file.length();
      final mimeType = _guessMime(f);

      // Step 1: Initialize upload - get presigned URL
      final initResult = await api.initUpload(
        filename: f.name,
        mimeType: mimeType,
        sizeBytes: fileSize,
        // Optional: domain and docType can be added later via UI
      );

      final storageKey = initResult['storage_key'] as String;
      final uploadUrl = initResult['upload_url'] as String;
      final uploadFields = initResult['upload_fields'] as Map<String, dynamic>?;
      final maxSizeBytes = initResult['max_size_bytes'] as int?;

      if (fileSize > (maxSizeBytes ?? fileSize)) {
        throw 'File size exceeds maximum allowed size';
      }

      // Step 2: Upload file to presigned URL
      await api.uploadToPresigned(
        url: uploadUrl,
        fields: uploadFields,
        filePath: f.path!,
        fileName: f.name,
        contentType: mimeType,
        onSendProgress: (sent, total) {
          setState(() {
            _progress = total > 0 ? sent / total : 0.0;
          });
        },
      );

      // Step 3: Notify backend that upload is complete
      final doc = await api.notifyUploaded(
        storageKey: storageKey,
        filename: f.name,
        mimeType: mimeType,
        sizeBytes: fileSize,
      );

      setState(() => _lastStatus = 'Uploaded: id=${doc['id']}');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Upload complete ✅')),
        );
      }
    } catch (e) {
      setState(() => _lastStatus = 'Upload failed: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    } finally {
      setState(() => _busy = false);
    }
  }

  String _guessMime(PlatformFile f) {
    final ext = (f.extension ?? '').toLowerCase();
    switch (ext) {
      case 'txt':
        return 'text/plain';
      case 'pdf':
        return 'application/pdf';
      case 'doc':
        return 'application/msword';
      case 'docx':
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      case 'xlsx':
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      case 'jpg':
      case 'jpeg':
        return 'image/jpeg';
      case 'png':
        return 'image/png';
      default:
        return 'application/octet-stream';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload Document')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            ElevatedButton.icon(
              onPressed: _busy ? null : _pickAndUpload,
              icon: const Icon(Icons.upload_file),
              label: Text(_busy ? 'Uploading...' : 'Pick & Upload'),
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(
                value: _busy ? (_progress.clamp(0.0, 1.0)) : null),
            const SizedBox(height: 12),
            Text(
              _busy
                  ? '${(_progress * 100).toStringAsFixed(0)}%'
                  : (_lastStatus ?? 'Idle'),
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}
