import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config.dart';
import '../services/api_client.dart';
import 'package:uuid/uuid.dart';

/// Diagnostics widget showing API base URL and last request ID
class ApiDiagnostics extends StatefulWidget {
  const ApiDiagnostics({super.key});

  @override
  State<ApiDiagnostics> createState() => _ApiDiagnosticsState();
}

class _ApiDiagnosticsState extends State<ApiDiagnostics> {
  String? _lastRequestId;
  String? _baseUrl;

  @override
  void initState() {
    super.initState();
    _baseUrl = kApiBase;
    // Try to get last request ID from ApiClient (would need to be stored)
    // For now, just show baseUrl
  }

  Future<void> _copyToClipboard(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Copied to clipboard'),
          duration: Duration(seconds: 1),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Icon(Icons.info_outline, size: 16),
                const SizedBox(width: 8),
                const Text(
                  'API Diagnostics',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 16),
                  onPressed: () => Navigator.of(context).pop(),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            _buildInfoRow('Base URL', _baseUrl ?? 'Unknown', _copyToClipboard),
            if (_lastRequestId != null)
              _buildInfoRow('Last Request ID', _lastRequestId!, _copyToClipboard),
            const SizedBox(height: 4),
            Text(
              'Cloud Run: ${kCloudRunApiBase.isNotEmpty ? "Yes" : "No"}',
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
            Text(
              'Test Mode: ${kTestMode ? "Yes" : "No"}',
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value, Function(String) onCopy) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: SelectableText(
              value,
              style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.copy, size: 14),
            onPressed: () => onCopy(value),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
            tooltip: 'Copy $label',
          ),
        ],
      ),
    );
  }
}

/// Show diagnostics as a dialog
void showApiDiagnostics(BuildContext context) {
  showDialog(
    context: context,
    builder: (context) => Dialog(
      child: const ApiDiagnostics(),
    ),
  );
}
