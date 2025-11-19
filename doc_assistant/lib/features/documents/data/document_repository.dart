import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../../../services/analysis_service.dart';
import '../../../services/api_client.dart';
import 'document.dart';

final documentRepoProvider = NotifierProvider<DocumentRepo, List<Document>>(DocumentRepo.new);
final selectedDocsProvider = StateProvider<Set<String>>((_) => <String>{});

final documentsProvider = Provider<List<Document>>((ref) => ref.watch(documentRepoProvider));
final documentByIdProvider = Provider.family<Document?, String>((ref, id) {
  final list = ref.watch(documentRepoProvider);
  return list.where((d) => d.id == id).firstOrNull;
});

class DocumentRepo extends Notifier<List<Document>> {
  final _uuid = const Uuid();

  @override
  List<Document> build() {
    // Seed with a couple of docs
    return [
      Document(id: '1', title: 'Welcome', excerpt: 'Structure & routing', body: 'Demo doc body here.'),
      Document(id: '2', title: 'Security Notes', excerpt: 'Storage & webhooks', body: 'Encrypt secrets, HMAC webhooks.'),
    ];
  }

  Future<List<Document>> listAllFromAccount() async {
    // TODO: call backend /docs
    await Future.delayed(const Duration(milliseconds: 150));
    return state;
  }

  Future<void> addDocumentsFromFiles(List<File> files) async {
    // TODO: call /upload for each file then merge result list from server
    final added = <Document>[];
    for (final f in files) {
      final id = _uuid.v4();
      added.add(Document(
        id: id,
        title: f.uri.pathSegments.last,
        excerpt: 'Uploaded file',
        body: 'No body (binary).',
        filename: f.path,
      ));
    }
    state = [...state, ...added];
  }

  Future<void> analyzeBatch(Set<String> ids) async {
    final client = ApiClient();
    final svc = AnalysisService(client.dio);

    // Simulate batch by iterating; replace with /analyze/batch backend call later
    final updated = [...state];
    for (final id in ids) {
      final idx = updated.indexWhere((d) => d.id == id);
      if (idx < 0) continue;
      final res = await svc.analyze(id);
      updated[idx] = updated[idx].copyWith(extracted: res);
    }
    state = updated;
  }
}

extension<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
