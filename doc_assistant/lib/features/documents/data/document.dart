class Document {
  final String id;
  final String title;
  final String excerpt;
  final String body;
  final Map<String, dynamic>? extracted; // analysis results (nullable)
  final String? filename; // original filename

  Document({
    required this.id,
    required this.title,
    required this.excerpt,
    required this.body,
    this.extracted,
    this.filename,
  });

  Document copyWith({
    String? id,
    String? title,
    String? excerpt,
    String? body,
    Map<String, dynamic>? extracted,
    String? filename,
  }) {
    return Document(
      id: id ?? this.id,
      title: title ?? this.title,
      excerpt: excerpt ?? this.excerpt,
      body: body ?? this.body,
      extracted: extracted ?? this.extracted,
      filename: filename ?? this.filename,
    );
  }
}
