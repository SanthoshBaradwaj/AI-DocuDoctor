import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/widgets/app_scaffold.dart';
import '../../theme/widgets/app_button.dart';
import '../../services/webhook_service.dart';
import '../../services/api_client.dart';
import '../../services/secure_storage_service.dart';
import '../../core/config.dart';

class WebhookPage extends ConsumerStatefulWidget {
  const WebhookPage({super.key});

  @override
  ConsumerState<WebhookPage> createState() => _WebhookPageState();
}

class _WebhookPageState extends ConsumerState<WebhookPage> {
  // ✅ declare controller here
  final TextEditingController _urlCtrl =
      TextEditingController(text: AppConfig.defaultWebhookUrl);

  String _lastStatus = '';

  @override
  void initState() {
    super.initState();
    _restoreUrl();
  }

  Future<void> _restoreUrl() async {
    final saved = await SecureStorageService.read('webhook_url');
    if (saved != null && saved.isNotEmpty) {
      setState(() => _urlCtrl.text = saved);
    }
  }

  Future<void> _saveUrl() async {
    await SecureStorageService.write('webhook_url', _urlCtrl.text.trim());
    setState(() => _lastStatus = 'Saved');
  }

  Future<void> _sendTest() async {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) {
      setState(() => _lastStatus = 'Enter a URL');
      return;
    }

    final client = ApiClient();
    final svc = WebhookService(client.dio);

    try {
      final res = await svc.send(
        url: url,
        payload: {
          'event': 'demo.test',
          'timestamp': DateTime.now().toIso8601String(),
          'data': {'message': 'Hello from Flutter baseline'}
        },
        headers: {'X-Env': 'dev'},
      );
      setState(() => _lastStatus = 'Status: ${res.statusCode}');
    } on DioException catch (e) {
      setState(() => _lastStatus = 'Error: ${e.message}');
    }
  }

  @override
  void dispose() {
    _urlCtrl.dispose(); // ✅ clean up controller
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'Webhooks',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(labelText: 'Webhook URL'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              AppButton(
                  label: 'Save URL', icon: Icons.save, onPressed: _saveUrl),
              const SizedBox(width: 12),
              AppButton(
                  label: 'Send Test', icon: Icons.send, onPressed: _sendTest),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _lastStatus,
            style: const TextStyle(color: Colors.white70),
          ),
        ],
      ),
    );
  }
}
