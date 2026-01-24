import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';
import '../../services/api_client.dart';
import '../../services/status_poller.dart';
import '../../models/api_error.dart';
import '../../widgets/error_dialog.dart';

class UploadPage extends StatefulWidget {
  const UploadPage({super.key});

  @override
  State<UploadPage> createState() => _UploadPageState();
}

class _UploadPageState extends State<UploadPage> {
  String? _selectedDomain;
  String? _selectedDocType;
  double _progress = 0.0;
  bool _busy = false;
  String? _lastStatus;
  String? _currentStep;

  static const _domains = [
    'IDENTITY',
    'IMMIGRATION',
    'INSURANCE',
    'VEHICLES',
    'FINANCE',
    'EMPLOYMENT_HR',
  ];

  // Document types by domain
  static const _docTypesByDomain = {
    'IDENTITY': ['PASSPORT', 'NATIONAL_ID', 'DRIVERS_LICENSE'],
    'IMMIGRATION': ['VISA', 'I94_OR_ENTRY_RECORD', 'I797_OR_STATUS_NOTICE'],
    'INSURANCE': [
      'HEALTH_INSURANCE_POLICY',
      'AUTO_INSURANCE_POLICY',
      'INSURANCE_ID_CARD'
    ],
    'VEHICLES': ['VEHICLE_REGISTRATION'],
    'FINANCE': [
      'BANK_STATEMENT',
      'CREDIT_CARD_STATEMENT',
      'LOAN_OR_MORTGAGE_AGREEMENT'
    ],
    'EMPLOYMENT_HR': [
      'PAYSLIP_OR_PAYSTUB',
      'EMPLOYMENT_CONTRACT',
      'BENEFITS_SUMMARY'
    ],
  };

  String _formatDomain(String domain) {
    return domain
        .replaceAll('_', ' ')
        .toLowerCase()
        .split(' ')
        .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  String _formatDocType(String docType) {
    return docType
        .replaceAll('_', ' ')
        .toLowerCase()
        .split(' ')
        .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  List<String> get _availableDocTypes {
    if (_selectedDomain == null) return [];
    return _docTypesByDomain[_selectedDomain] ?? [];
  }

  Future<void> _pickAndUpload() async {
    if (_selectedDomain == null || _selectedDocType == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Please select both domain and document type')),
      );
      return;
    }

    setState(() {
      _progress = 0.0;
      _busy = true;
      _lastStatus = null;
      _currentStep = null;
    });

    try {
      final picked = await FilePicker.platform.pickFiles(
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
        withData: true,
      );
      if (picked == null) {
        setState(() => _busy = false);
        return;
      }
      final f = picked.files.first;

      // On web, f.path throws - only use f.bytes
      // On mobile/desktop, use f.path
      if (kIsWeb && f.bytes == null) {
        throw 'Web upload requires file bytes';
      }
      if (!kIsWeb && f.path == null) {
        throw 'Mobile/desktop upload requires file path';
      }

      final api = ApiClient();
      final fileSize = f.size;
      final mimeType = _guessMime(f);

      // Step A: Initialize upload - get presigned URL
      setState(() => _currentStep = 'Initializing upload...');
      final initResult = await api.initUpload(UploadInitIn(
        filename: f.name,
        mimeType: mimeType,
        sizeBytes: fileSize,
        domain: _selectedDomain,
        docType: _selectedDocType,
      ));

      final storageKey = initResult.storageKey;
      final uploadUrl = initResult.uploadUrl;

      if (fileSize > initResult.maxSizeBytes) {
        throw 'File size exceeds maximum allowed size (${initResult.maxSizeBytes} bytes)';
      }

      // Step B: Upload file to presigned URL (GCS requires HTTP PUT with raw bytes)
      setState(() {
        _currentStep = 'Uploading to storage...';
        _progress = 0.1;
      });

      // GCS signed URLs require HTTP PUT with raw bytes and Content-Type header
      if (kIsWeb) {
        // Web: use bytes directly
        final bytes = f.bytes;
        if (bytes == null) {
          throw Exception("Web upload requires bytes, found null");
        }

        await api.uploadBytesToPresigned(
          url: uploadUrl,
          bytes: bytes,
          contentType: mimeType,
          onSendProgress: (sent, total) {
            setState(() {
              _progress = 0.1 + (sent / total) * 0.7; // 10% to 80%
            });
          },
        );
      } else {
        // Mobile/Desktop: use file path
        // Never access f.path on web - it throws
        final filePath = f.path;
        if (filePath == null) {
          throw 'File path is null';
        }

        await api.uploadToPresigned(
          url: uploadUrl,
          filePath: filePath,
          fileName: f.name,
          contentType: mimeType,
          onSendProgress: (sent, total) {
            setState(() {
              _progress = 0.1 + (sent / total) * 0.7; // 10% to 80%
            });
          },
        );
      }

      // Step C: Notify backend that upload is complete
      setState(() {
        _currentStep = 'Notifying backend...';
        _progress = 0.9;
      });

      final doc = await api.notifyUploaded(UploadNotifyIn(
        storageKey: storageKey,
        filename: f.name,
        mimeType: mimeType,
        sizeBytes: fileSize,
        domain: _selectedDomain,
        docType: _selectedDocType,
      ));

      // Step D: Poll status until ready
      setState(() {
        _currentStep = 'Processing document (OCR)...';
        _progress = 0.95;
      });

      final poller = StatusPoller(api);
      try {
        await poller.pollUntilReady(
          docId: doc.id,
          interval: const Duration(seconds: 2),
          timeout: const Duration(minutes: 5),
          onStatusUpdate: (status) {
            if (mounted) {
              setState(() {
                if (status.ocrStatus == 'processing') {
                  _currentStep = 'Processing document (OCR)...';
                } else if (status.ocrStatus == 'ready' &&
                    status.llmStatus == 'processing') {
                  _currentStep = 'Processing document (LLM analysis)...';
                } else if (status.isReady) {
                  _currentStep = 'Document ready!';
                }
              });
            }
          },
        );

        setState(() {
          _progress = 1.0;
          _lastStatus = 'Upload complete! Document ID: ${doc.id}';
          _currentStep = null;
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Upload complete ✅')),
          );
          // Navigate to chat screen
          context.go('/chat/${doc.id}');
        }
      } catch (e) {
        if (mounted) {
          if (e is ApiError) {
            ErrorDialog.show(context, e, title: 'Processing Error');
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Processing failed: $e')),
            );
          }
        }
        // Still navigate to document detail even if polling failed
        if (mounted) {
          context.go('/docs/${doc.id}');
        }
      }
    } on DioException catch (e) {
      ApiError? apiError;
      if (e.response != null) {
        final data = e.response!.data;
        if (data is Map<String, dynamic> && data.containsKey('error_code')) {
          apiError = ApiError.fromJson(data);
        }
      }

      if (mounted) {
        if (apiError != null) {
          ErrorDialog.show(context, apiError, title: 'Upload Error');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content:
                    Text('Upload failed: ${e.message ?? "Unknown error"}')),
          );
        }
      }
    } catch (e) {
      setState(() {
        _lastStatus = 'Upload failed: $e';
        _currentStep = null;
      });
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
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Domain selection
            const Text('Domain',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _domains.map((domain) {
                return ChoiceChip(
                  label: Text(_formatDomain(domain)),
                  selected: _selectedDomain == domain,
                  onSelected: (selected) {
                    setState(() {
                      _selectedDomain = selected ? domain : null;
                      _selectedDocType =
                          null; // Reset doc type when domain changes
                    });
                  },
                );
              }).toList(),
            ),
            const SizedBox(height: 24),
            // Document type selection
            const Text('Document Type',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (_selectedDomain == null)
              const Text('Please select a domain first',
                  style: TextStyle(color: Colors.grey))
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _availableDocTypes.map((docType) {
                  return ChoiceChip(
                    label: Text(_formatDocType(docType)),
                    selected: _selectedDocType == docType,
                    onSelected: (selected) {
                      setState(() {
                        _selectedDocType = selected ? docType : null;
                      });
                    },
                  );
                }).toList(),
              ),
            const SizedBox(height: 24),
            // Upload button
            ElevatedButton.icon(
              onPressed:
                  (_busy || _selectedDomain == null || _selectedDocType == null)
                      ? null
                      : _pickAndUpload,
              icon: const Icon(Icons.upload_file),
              label: Text(_busy ? 'Uploading...' : 'Pick & Upload'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
            const SizedBox(height: 16),
            // Progress indicator
            if (_busy) ...[
              if (_currentStep != null)
                Text(_currentStep!,
                    style: const TextStyle(fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              LinearProgressIndicator(value: _progress.clamp(0.0, 1.0)),
              const SizedBox(height: 8),
              Text('${(_progress * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ] else if (_lastStatus != null)
              Text(_lastStatus!,
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
