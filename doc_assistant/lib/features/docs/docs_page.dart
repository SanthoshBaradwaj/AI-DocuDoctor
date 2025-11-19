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
  late Future<List<dynamic>> _future;
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

  Future<List<dynamic>> _loadDocs() async {
    return ApiClient().listDocs(domain: _selectedDomain);
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
            onPressed: () => context.go('/home/upload'),
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
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return Center(child: Text('Error: ${snap.error}'));
                }
                final items = snap.data ?? const [];
                if (items.isEmpty) {
                  return const Center(
                      child: Text('No documents yet. Tap the upload icon.'));
                }
                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final docData = items[i] as Map<String, dynamic>;
                      final doc = Doc.fromJson(docData);
                      final id = doc.id;
                      final title = doc.title;
                      final status = doc.status;
                      final domain = doc.domain;
                      final docType = doc.docType;
                      final excerpt = doc.excerpt;
                      final expiryDate = doc.expiryDate;

                      return ListTile(
                        title: Text(title),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (domain != null || docType != null)
                              Text(
                                [
                                  if (domain != null) _formatDomain(domain),
                                  if (docType != null) _formatDocType(docType),
                                ].join(' • '),
                                style: const TextStyle(
                                    fontWeight: FontWeight.w500, fontSize: 12),
                              ),
                            const SizedBox(height: 4),
                            Text(
                              '$status${expiryDate != null ? ' • Expires: ${expiryDate.toString().split(' ')[0]}' : ''}',
                              style: const TextStyle(fontSize: 12),
                            ),
                            if (excerpt.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                excerpt.length > 80
                                    ? '${excerpt.substring(0, 80)}…'
                                    : excerpt,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 12),
                              ),
                            ],
                          ],
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.go('/home/docs/detail/$id'),
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
