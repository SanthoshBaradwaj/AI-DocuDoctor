import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../theme/widgets/app_scaffold.dart';
import '../data/document_repository.dart';
import '../../chat/doc_chat_widget.dart';

class DocumentDetailPage extends ConsumerWidget {
  final String docId;
  const DocumentDetailPage({super.key, required this.docId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final doc = ref.watch(documentByIdProvider(docId));

    return AppScaffold(
      title: doc?.title ?? 'Document',
      body: doc == null
          ? const Center(child: Text('Not found', style: TextStyle(color: Colors.white)))
          : ListView(
              children: [
                Text(doc.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white)),
                const SizedBox(height: 10),
                Text(doc.body, style: const TextStyle(color: Colors.white70)),
                const SizedBox(height: 16),
                Text('Extracted information', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white)),
                const SizedBox(height: 8),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      (doc.extracted ?? {'status': 'Not analyzed yet'}).toString(),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                DocChatWidget(docId: docId),
              ],
            ),
    );
  }
}
