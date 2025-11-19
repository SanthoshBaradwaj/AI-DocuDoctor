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
  late Future<DocDetail> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient().fetchDocDetail(widget.docId);
  }

  Future<void> _reload() async {
    setState(() {
      _future = ApiClient().fetchDocDetail(widget.docId);
    });
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
      body: FutureBuilder<DocDetail>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
                child: Text('Error: ${snap.error}',
                    style: const TextStyle(color: Colors.red)));
          }
          final doc = snap.data!;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(doc.title,
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                if (doc.domain != null || doc.docType != null) ...[
                  Text('Domain: ${_formatDomain(doc.domain)}'),
                  Text('Type: ${_formatDocType(doc.docType)}'),
                  const SizedBox(height: 4),
                ],
                Text('Status: ${doc.status}'),
                Text('File: ${doc.filename}'),
                if (doc.expiryDate != null)
                  Text('Expiry: ${doc.expiryDate!.toString().split(' ')[0]}'),
                const SizedBox(height: 12),
                if (doc.excerpt.isNotEmpty) ...[
                  const Text('Excerpt',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(doc.excerpt),
                  const SizedBox(height: 12),
                ],
                if (doc.extracted != null && doc.extracted!.isNotEmpty) ...[
                  const Text('Extracted Fields',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  ...doc.extracted!.entries.map((entry) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('${entry.key}: ',
                                style: const TextStyle(
                                    fontWeight: FontWeight.w500)),
                            Expanded(
                              child: Text(entry.value.toString()),
                            ),
                          ],
                        ),
                      )),
                  const SizedBox(height: 12),
                ],
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => context.go('/chat?docId=${widget.docId}'),
                    icon: const Icon(Icons.chat_bubble_outline),
                    label: const Text('Chat About This Document'),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
