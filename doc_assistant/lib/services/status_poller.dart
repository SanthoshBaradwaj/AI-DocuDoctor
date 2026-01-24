import 'dart:async';
import '../models/doc_status.dart';
import 'api_client.dart';

/// Service for polling document status until ready
class StatusPoller {
  final ApiClient _apiClient;
  Timer? _timer;
  bool _isPolling = false;

  StatusPoller(this._apiClient);

  /// Poll document status until ready or error
  /// Returns the final DocStatus
  /// Throws if polling times out or encounters an error
  Future<DocStatus> pollUntilReady({
    required String docId,
    Duration interval = const Duration(seconds: 2),
    Duration timeout = const Duration(minutes: 5),
    void Function(DocStatus status)? onStatusUpdate,
  }) async {
    if (_isPolling) {
      throw StateError('Already polling a document');
    }

    _isPolling = true;
    final startTime = DateTime.now();
    final completer = Completer<DocStatus>();

    try {
      while (true) {
        // Check timeout
        if (DateTime.now().difference(startTime) > timeout) {
          _isPolling = false;
          throw TimeoutException('Status polling timed out after ${timeout.inSeconds} seconds');
        }

        // Fetch status
        final status = await _apiClient.fetchDocStatus(docId);
        
        // Notify listener
        onStatusUpdate?.call(status);

        // Check if ready
        if (status.isReady) {
          _isPolling = false;
          return status;
        }

        // Check if error
        if (status.hasError) {
          _isPolling = false;
          throw Exception('Document processing failed: ${status.lastError ?? "Unknown error"}');
        }

        // Wait before next poll
        await Future.delayed(interval);
      }
    } catch (e) {
      _isPolling = false;
      if (!completer.isCompleted) {
        completer.completeError(e);
      }
      rethrow;
    }
  }

  /// Stop polling (if active)
  void stop() {
    _timer?.cancel();
    _timer = null;
    _isPolling = false;
  }

  /// Check if currently polling
  bool get isPolling => _isPolling;
}
