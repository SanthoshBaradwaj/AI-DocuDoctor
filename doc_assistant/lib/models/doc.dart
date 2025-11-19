class Doc {
  final int id;
  final String title;
  final String filename;
  final String status;
  final String excerpt;
  final String? domain; // DocumentDomain enum value
  final String? docType; // DocumentType enum value
  final DateTime? expiryDate;
  final Map<String, dynamic>? extracted;

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
      id: j['id'] as int,
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
      };
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
      id: j['id'] as int,
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
    );
  }

  @override
  Map<String, dynamic> toJson() => {
        ...super.toJson(),
        'body': body,
      };
}
