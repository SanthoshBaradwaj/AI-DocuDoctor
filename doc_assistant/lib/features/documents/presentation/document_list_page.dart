import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../theme/widgets/app_scaffold.dart';
import '../../documents/data/document_repository.dart';

class DocumentListPage extends ConsumerWidget {
  const DocumentListPage({super.key});

  Future<void> _pickAndUpload(WidgetRef ref) async {
    final result = await FilePicker.platform
        .pickFiles(allowMultiple: true, withData: false);
    if (result == null) return;
    final files = result.paths.whereType<String>().map((p) => File(p)).toList();
    await ref.read(documentRepoProvider.notifier).addDocumentsFromFiles(files);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docs = ref.watch(documentsProvider);
    final selected = ref.watch(selectedDocsProvider);

    return AppScaffold(
      title: 'Documents',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 8, runSpacing: 8, children: [
            ElevatedButton.icon(
              onPressed: () => _pickAndUpload(ref),
              icon: const Icon(Icons.upload_file),
              label: const Text('Upload files'),
            ),
            ElevatedButton.icon(
              onPressed: selected.isEmpty
                  ? null
                  : () => ref
                      .read(documentRepoProvider.notifier)
                      .analyzeBatch(selected),
              icon: const Icon(Icons.analytics),
              label: Text('Extract (${selected.length})'),
            ),
            TextButton(
              onPressed: () =>
                  ref.read(selectedDocsProvider.notifier).state = <String>{},
              child: const Text('Clear selection'),
            ),
          ]),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.separated(
              itemCount: docs.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, i) {
                final d = docs[i];
                final isSel = selected.contains(d.id);
                return Card(
                  child: ListTile(
                    leading: Checkbox(
                      value: isSel,
                      onChanged: (v) {
                        final set = {...selected};
                        v == true ? set.add(d.id) : set.remove(d.id);
                        ref.read(selectedDocsProvider.notifier).state = set;
                      },
                    ),
                    title: Text(d.title),
                    subtitle: Text(
                      d.excerpt +
                          (d.extracted != null ? '  •  Extracted ✓' : ''),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.go('/docs/${d.id}'),
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
