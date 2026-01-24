class Doc {
  final String id;
  final String title;
  final String filename;
  final String status;
  final String excerpt;
  final String? domain; // DocumentDomain enum value
  final String? docType; // DocumentType enum value
  final DateTime? expiryDate;
  final Map<String, dynamic>? extracted;
  final String?
      ocrStatus; // OCR pipeline status: pending, processing, ready, error
  final String?
      llmStatus; // LLM pipeline status: pending, processing, ready, error

  Doc({
    required this.id,
    required this.title,
    required this.filename,
    required this.status,
    required this.excerpt,
    this.domain,
    this.docType,
    this.expiryDate,
    this.extracted,
    this.ocrStatus,
    this.llmStatus,
  });

  factory Doc.fromJson(Map<String, dynamic> j) {
    DateTime? parseExpiryDate(dynamic value) {
      if (value == null) return null;
      if (value is String) {
        try {
          return DateTime.parse(value);
        } catch (e) {
          return null;
        }
      }
      return null;
    }

    return Doc(
      id: j['id']
          .toString(), // Backend returns string IDs (or int that we convert)
      title: (j['title'] ?? '') as String,
      filename: (j['filename'] ?? '') as String,
      status: (j['status'] ?? '') as String,
      excerpt: (j['excerpt'] ?? '') as String,
      domain: j['domain'] as String?,
      docType: j['doc_type'] as String?,
      expiryDate: parseExpiryDate(j['expiry_date']),
      extracted: (j['extracted'] is Map)
          ? (j['extracted'] as Map).cast<String, dynamic>()
          : null,
      ocrStatus: j['ocr_status'] as String?,
      llmStatus: j['llm_status'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'filename': filename,
        'status': status,
        'excerpt': excerpt,
        if (domain != null) 'domain': domain,
        if (docType != null) 'doc_type': docType,
        if (expiryDate != null) 'expiry_date': expiryDate!.toIso8601String(),
        if (extracted != null) 'extracted': extracted,
        if (ocrStatus != null) 'ocr_status': ocrStatus,
        if (llmStatus != null) 'llm_status': llmStatus,
      };

  /// Check if chat is available (OCR ready and LLM ready)
  bool get isChatAvailable {
    return ocrStatus == 'ready' && llmStatus == 'ready';
  }

  /// Check if document is still processing
  bool get isProcessing {
    return ocrStatus == 'processing' ||
        llmStatus == 'processing' ||
        status == 'processing';
  }
}

class DocDetail extends Doc {
  final String body;

  DocDetail({
    required super.id,
    required super.title,
    required super.filename,
    required super.status,
    required super.excerpt,
    required this.body,
    super.domain,
    super.docType,
    super.expiryDate,
    super.extracted,
    super.ocrStatus,
    super.llmStatus,
  });

  factory DocDetail.fromJson(Map<String, dynamic> j) {
    DateTime? parseExpiryDate(dynamic value) {
      if (value == null) return null;
      if (value is String) {
        try {
          return DateTime.parse(value);
        } catch (e) {
          return null;
        }
      }
      return null;
    }

    return DocDetail(
      id: j['id'].toString(), // Backend returns string IDs
      title: (j['title'] ?? '') as String,
      filename: (j['filename'] ?? '') as String,
      status: (j['status'] ?? '') as String,
      excerpt: (j['excerpt'] ?? '') as String,
      body: (j['body'] ?? '') as String,
      domain: j['domain'] as String?,
      docType: j['doc_type'] as String?,
      expiryDate: parseExpiryDate(j['expiry_date']),
      extracted: (j['extracted'] is Map)
          ? (j['extracted'] as Map).cast<String, dynamic>()
          : null,
      ocrStatus: j['ocr_status'] as String?,
      llmStatus: j['llm_status'] as String?,
    );
  }

  @override
  Map<String, dynamic> toJson() => {
        ...super.toJson(),
        'body': body,
      };
}
