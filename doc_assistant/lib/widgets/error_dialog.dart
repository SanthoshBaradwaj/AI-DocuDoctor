import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/api_error.dart';

/// Error dialog that shows error message and request_id with copy button
class ErrorDialog extends StatelessWidget {
  final ApiError error;
  final String? title;

  const ErrorDialog({
    super.key,
    required this.error,
    this.title,
  });

  static Future<void> show(BuildContext context, ApiError error, {String? title}) {
    return showDialog(
      context: context,
      builder: (context) => ErrorDialog(error: error, title: title),
    );
  }

  Future<void> _copyRequestId(BuildContext context) async {
    if (error.requestId != null) {
      await Clipboard.setData(ClipboardData(text: error.requestId!));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Request ID copied to clipboard'),
            duration: Duration(seconds: 2),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(title ?? 'Error'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              error.friendlyMessage,
              style: const TextStyle(fontSize: 16),
            ),
            if (error.requestId != null) ...[
              const SizedBox(height: 16),
              const Text(
                'Request ID:',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  Expanded(
                    child: SelectableText(
                      error.requestId!,
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: Colors.grey,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.copy, size: 20),
                    onPressed: () => _copyRequestId(context),
                    tooltip: 'Copy Request ID',
                  ),
                ],
              ),
            ],
            if (error.details != null && error.details!.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text(
                'Details:',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                error.details.toString(),
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('OK'),
        ),
      ],
    );
  }
}

/// Error toast/snackbar with request_id
class ErrorToast {
  static void show(BuildContext context, ApiError error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(error.friendlyMessage),
            if (error.requestId != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  'Request ID: ${error.requestId}',
                  style: const TextStyle(fontSize: 12, color: Colors.white70),
                ),
              ),
          ],
        ),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 5),
        action: error.requestId != null
            ? SnackBarAction(
                label: 'Copy ID',
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: error.requestId!));
                },
              )
            : null,
      ),
    );
  }
}
