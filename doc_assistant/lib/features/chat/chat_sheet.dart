import 'package:flutter/material.dart';
import '../../services/api_client.dart';
import '../../models/chat.dart';

class ChatSheet extends StatefulWidget {
  final int docId;
  const ChatSheet({super.key, required this.docId});

  @override
  State<ChatSheet> createState() => _ChatSheetState();
}

class _ChatSheetState extends State<ChatSheet> {
  final api = ApiClient();
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  final _msgs = <ChatMessage>[];

  Future<void> _send() async {
    final txt = _ctrl.text.trim();
    if (txt.isEmpty) return;
    setState(() {
      _msgs.add(ChatMessage('user', txt));
      _ctrl.clear();
    });
    await Future.delayed(Duration.zero);
    _scroll.animateTo(_scroll.position.maxScrollExtent + 80,
        duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
    try {
      final response = await api.chatWithDocument(
        docId: widget.docId,
        messages: _msgs.map((m) => m.toJson()).toList(),
      );
      final reply = response['reply'] as String? ?? '';
      setState(() => _msgs.add(ChatMessage('assistant', reply)));
    } catch (e) {
      setState(() => _msgs.add(ChatMessage('assistant', 'Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 8,
      child: SizedBox(
        height: 220,
        child: Column(
          children: [
            Expanded(
              child: ListView.builder(
                controller: _scroll,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                itemCount: _msgs.length,
                itemBuilder: (c, i) {
                  final m = _msgs[i];
                  final isUser = m.role == 'user';
                  return Align(
                    alignment:
                        isUser ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      padding: const EdgeInsets.all(10),
                      constraints: const BoxConstraints(maxWidth: 320),
                      decoration: BoxDecoration(
                        color: isUser
                            ? Theme.of(context)
                                .colorScheme
                                .primary
                                .withOpacity(.12)
                            : Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(m.content),
                    ),
                  );
                },
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 6, 8, 10),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      decoration: const InputDecoration(
                        hintText: 'Ask something about this doc…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.icon(
                      onPressed: _send,
                      icon: const Icon(Icons.send),
                      label: const Text('Send')),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
