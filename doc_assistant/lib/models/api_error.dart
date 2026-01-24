/// API Error model matching backend normalized error envelope
/// {error_code: string, message: string, details: object|null, request_id: string}
class ApiError {
  final String errorCode;
  final String message;
  final Map<String, dynamic>? details;
  final String? requestId;

  ApiError({
    required this.errorCode,
    required this.message,
    this.details,
    this.requestId,
  });

  factory ApiError.fromJson(Map<String, dynamic> json) {
    return ApiError(
      errorCode: json['error_code'] as String? ?? 'UNKNOWN_ERROR',
      message: json['message'] as String? ?? 'An error occurred',
      details: json['details'] as Map<String, dynamic>?,
      requestId: json['request_id'] as String?,
    );
  }

  /// Create a user-friendly error message
  String get friendlyMessage {
    // Map error codes to friendly messages
    switch (errorCode) {
      case 'LLM_TIMEOUT':
        return 'The AI service took too long to respond. Please try again.';
      case 'LLM_UNREACHABLE':
        return 'Unable to reach the AI service. Please check your connection.';
      case 'LLM_UPSTREAM_ERROR':
        return 'The AI service encountered an error. Please try again later.';
      case 'LLM_BAD_RESPONSE':
        return 'Received an invalid response from the AI service.';
      case 'VALIDATION_ERROR':
        return 'Invalid input. Please check your request and try again.';
      case 'NOT_FOUND':
        return 'The requested resource was not found.';
      case 'REPLY_TOO_LONG':
        return 'The response is too long. Please try a different question.';
      case 'PAYLOAD_TOO_LARGE':
        return 'The file is too large. Please upload a smaller file.';
      case 'RATE_LIMIT_EXCEEDED':
        return 'Too many requests. Please wait a moment and try again.';
      case 'INTERNAL_ERROR':
        return 'An internal error occurred. Please try again later.';
      default:
        return message;
    }
  }

  Map<String, dynamic> toJson() => {
        'error_code': errorCode,
        'message': message,
        if (details != null) 'details': details,
        if (requestId != null) 'request_id': requestId,
      };

  @override
  String toString() => 'ApiError($errorCode): $message';
}
