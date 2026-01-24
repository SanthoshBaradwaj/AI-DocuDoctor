/// Document status response model
class DocStatus {
  final String id;
  final String status;
  final String ocrStatus;
  final String llmStatus;
  final String? lastError;

  DocStatus({
    required this.id,
    required this.status,
    required this.ocrStatus,
    required this.llmStatus,
    this.lastError,
  });

  factory DocStatus.fromJson(Map<String, dynamic> json) {
    return DocStatus(
      id: json['id'].toString(), // Backend returns string IDs
      status: json['status'] as String? ?? 'unknown',
      ocrStatus: json['ocr_status'] as String? ?? 'pending',
      llmStatus: json['llm_status'] as String? ?? 'pending',
      lastError: json['last_error'] as String?,
    );
  }

  /// Check if document is ready for chat
  bool get isReady {
    return ocrStatus == 'ready' && llmStatus == 'ready';
  }

  /// Check if document is still processing
  bool get isProcessing {
    return ocrStatus == 'processing' || llmStatus == 'processing' || status == 'processing';
  }

  /// Check if there was an error
  bool get hasError {
    return ocrStatus == 'error' || llmStatus == 'error' || status == 'error';
  }
}
