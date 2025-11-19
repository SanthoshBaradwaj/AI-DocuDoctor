import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api_client.dart';
import '../../models/doc.dart';
import '../../widgets/doc_card.dart';
import '../../services/session.dart';

class DocsListPage extends StatefulWidget {
  const DocsListPage({super.key});
  @override State<DocsListPage> createState() => _DocsListPageState();
}

class _DocsListPageState extends State<DocsListPage> {
  final api = ApiClient();
  late Future<List<Doc>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Doc>> _load() async {
    final list = await api.listDocs();
    return list.map((j) => Doc.fromJson(Map<String, dynamic>.from(j))).toList();
  }

  Future<void> _logout() async {
    await Session.logout();
    if (mounted) context.go('/auth/login');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Your Documents'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () => setState(() => _future = _load())),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/upload').then((_) => setState(() => _future = _load())),
        icon: const Icon(Icons.upload_file),
        label: const Text('Upload'),
      ),
      body: FutureBuilder<List<Doc>>(
        future: _future,
        builder: (c, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final items = snap.data ?? [];
          if (items.isEmpty) {
            return const Center(child: Text('No documents yet. Tap Upload to add one.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (c, i) => DocCard(
              doc: items[i],
              onTap: () => context.push('/doc/${items[i].id}'),
            ),
          );
        },
      ),
    );
  }
}
