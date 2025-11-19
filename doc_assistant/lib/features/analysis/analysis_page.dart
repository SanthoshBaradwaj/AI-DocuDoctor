import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/widgets/app_scaffold.dart';
import '../../theme/widgets/app_button.dart';
import '../../services/api_client.dart';
import '../../services/analysis_service.dart';

class AnalysisPage extends ConsumerStatefulWidget {
  const AnalysisPage({super.key});

  @override
  ConsumerState<AnalysisPage> createState() => _AnalysisPageState();
}

class _AnalysisPageState extends ConsumerState<AnalysisPage> {
  final _docIdCtrl = TextEditingController(text: '1');
  String _status = 'Enter a docId and hit Analyze';
  Map<String, dynamic>? _result;

  Future<void> _run() async {
    final client = ApiClient();
    final svc = AnalysisService(client.dio);
    setState(() {
      _status = 'Running analysis...';
      _result = null;
    });
    try {
      final data = await svc.analyze(_docIdCtrl.text.trim());
      setState(() {
        _result = data;
        _status = 'Done';
      });
    } catch (e) {
      setState(() => _status = 'Failed: $e');
    }
  }

  @override
  void dispose() {
    _docIdCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'Analysis',
      body: ListView(
        children: [
          TextField(
            controller: _docIdCtrl,
            decoration: const InputDecoration(labelText: 'Document ID'),
          ),
          const SizedBox(height: 12),
          AppButton(label: 'Analyze', icon: Icons.analytics, onPressed: _run),
          const SizedBox(height: 12),
          Text(_status, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 12),
          if (_result != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_result.toString()),
              ),
            ),
        ],
      ),
    );
  }
}
