import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api_client.dart';
import '../../models/doc.dart';

class DocsPage extends StatefulWidget {
  const DocsPage({super.key});

  @override
  State<DocsPage> createState() => _DocsPageState();
}

class _DocsPageState extends State<DocsPage> {
  late Future<List<Doc>> _future;
  String? _selectedDomain;

  static const _domains = [
    'IDENTITY',
    'IMMIGRATION',
    'INSURANCE',
    'VEHICLES',
    'FINANCE',
    'EMPLOYMENT_HR',
  ];

  @override
  void initState() {
    super.initState();
    _future = _loadDocs();
  }

  Future<List<Doc>> _loadDocs() async {
    return ApiClient().fetchDocs(domain: _selectedDomain);
  }

  Future<void> _refresh() async {
    setState(() {
      _future = _loadDocs();
    });
  }

  void _onDomainFilter(String? domain) {
    setState(() {
      _selectedDomain = domain;
      _future = _loadDocs();
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

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'ready':
        return Colors.green;
      case 'processing':
        return Colors.orange;
      case 'error':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Documents'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.upload_file),
            onPressed: () => context.go('/upload'),
            tooltip: 'Upload',
          ),
        ],
      ),
      body: Column(
        children: [
          // Domain filter chips
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  FilterChip(
                    label: const Text('All'),
                    selected: _selectedDomain == null,
                    onSelected: (_) => _onDomainFilter(null),
                  ),
                  const SizedBox(width: 8),
                  ..._domains.map((domain) => Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(_formatDomain(domain)),
                          selected: _selectedDomain == domain,
                          onSelected: (_) => _onDomainFilter(domain),
                        ),
                      )),
                ],
              ),
            ),
          ),
          const Divider(height: 1),
          // Documents list
          Expanded(
            child: FutureBuilder<List<Doc>>(
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
                final docs = snap.data ?? [];
                if (docs.isEmpty) {
                  return const Center(
                      child: Text('No documents yet. Tap the upload icon.'));
                }
                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView.separated(
                    itemCount: docs.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final doc = docs[i];
                      return ListTile(
                        title: Text(doc.title),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (doc.domain != null || doc.docType != null)
                              Text(
                                [
                                  if (doc.domain != null)
                                    _formatDomain(doc.domain),
                                  if (doc.docType != null)
                                    _formatDocType(doc.docType),
                                ].join(' • '),
                                style: const TextStyle(
                                    fontWeight: FontWeight.w500, fontSize: 12),
                              ),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: _getStatusColor(doc.status)
                                        .withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    doc.status.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      color: _getStatusColor(doc.status),
                                    ),
                                  ),
                                ),
                                if (doc.expiryDate != null) ...[
                                  const SizedBox(width: 8),
                                  Text(
                                    'Expires: ${doc.expiryDate!.toString().split(' ')[0]}',
                                    style: const TextStyle(fontSize: 12),
                                  ),
                                ],
                              ],
                            ),
                            if (doc.excerpt.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                doc.excerpt.length > 80
                                    ? '${doc.excerpt.substring(0, 80)}…'
                                    : doc.excerpt,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 12),
                              ),
                            ],
                          ],
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.go('/docs/${doc.id}'),
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
