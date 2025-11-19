import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api_client.dart';
import '../../models/doc.dart';

class DocDetailPage extends StatefulWidget {
  final int docId;
  const DocDetailPage({super.key, required this.docId});

  @override
  State<DocDetailPage> createState() => _DocDetailPageState();
}

class _DocDetailPageState extends State<DocDetailPage> {
  late Future<Map<String, dynamic>> _future;
  bool _analyzing = false;

  @override
  void initState() {
    super.initState();
    _future = ApiClient().getDocDetail(widget.docId);
  }

  Future<void> _reload() async {
    setState(() {
      _future = ApiClient().getDocDetail(widget.docId);
    });
  }

  Future<void> _analyze() async {
    setState(() => _analyzing = true);
    try {
      await ApiClient().analyzeOne(widget.docId);
      await _reload();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Analysis updated')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Analyze failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _analyzing = false);
    }
  }

  String _formatDomain(String? domain) {
    if (domain == null) return '';
    return domain
        .replaceAll('_', ' ')
        .toLowerCase()
        .split(' ')
        .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  String _formatDocType(String? docType) {
    if (docType == null) return '';
    return docType
        .replaceAll('_', ' ')
        .toLowerCase()
        .split(' ')
        .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Doc #${widget.docId}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _reload,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final docData = snap.data!;
          final doc = DocDetail.fromJson(docData);
          final title = doc.title;
          final status = doc.status;
          final filename = doc.filename;
          final mime = docData['mime'] ?? docData['mime_type'] ?? '';
          final size = docData['size'] ?? docData['size_bytes'] ?? 0;
          final excerpt = doc.excerpt;
          final extracted = doc.extracted;
          final domain = doc.domain;
          final docType = doc.docType;
          final expiryDate = doc.expiryDate;

          return Padding(
            padding: const EdgeInsets.all(16),
            child: ListView(
              children: [
                Text(title,
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                if (domain != null || docType != null) ...[
                  Text('Domain: ${_formatDomain(domain)}'),
                  Text('Type: ${_formatDocType(docType)}'),
                  const SizedBox(height: 4),
                ],
                Text('Status: $status'),
                Text('File: $filename'),
                if (mime.isNotEmpty) Text('MIME: $mime'),
                Text('Size: $size bytes'),
                if (expiryDate != null)
                  Text('Expiry: ${expiryDate.toString().split(' ')[0]}'),
                const SizedBox(height: 12),
                if (excerpt.isNotEmpty) ...[
                  const Text('Excerpt',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(excerpt),
                  const SizedBox(height: 12),
                ],
                if (extracted != null && extracted.isNotEmpty) ...[
                  const Text('Extracted',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(extracted.toString()),
                  const SizedBox(height: 12),
                ],
                Row(
                  children: [
                    ElevatedButton.icon(
                      onPressed: _analyzing ? null : _analyze,
                      icon: const Icon(Icons.insights),
                      label: Text(_analyzing ? 'Analyzing…' : 'Analyze'),
                    ),
                    const SizedBox(width: 12),
                    OutlinedButton.icon(
                      onPressed: () =>
                          context.go('/home/chat?docId=${widget.docId}'),
                      icon: const Icon(Icons.chat_bubble_outline),
                      label: const Text('Chat'),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
