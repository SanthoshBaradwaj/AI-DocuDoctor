import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'chat_controller.dart';

class DocChatWidget extends ConsumerStatefulWidget {
  final String docId;
  const DocChatWidget({super.key, required this.docId});

  @override
  ConsumerState<DocChatWidget> createState() => _DocChatWidgetState();
}

class _DocChatWidgetState extends ConsumerState<DocChatWidget> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final msgs = ref.watch(docChatControllerProvider(widget.docId));
    return Column(
      children: [
        const SizedBox(height: 8),
        Text('Chat about this document',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Container(
          height: 220,
          decoration: BoxDecoration(
            color: Theme.of(context).cardColor,
            borderRadius: BorderRadius.circular(12),
          ),
          child: ListView.separated(
            padding: const EdgeInsets.all(10),
            itemCount: msgs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (context, i) {
              final m = msgs[i];
              final isUser = m.role == 'user';
              return Align(
                alignment:
                    isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: isUser
                        ? Theme.of(context).colorScheme.primary
                        : Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(m.content,
                      style: TextStyle(color: isUser ? Colors.white : null)),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
                child: TextField(
                    controller: _input,
                    decoration: const InputDecoration(hintText: 'Message...'))),
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: () async {
                final text = _input.text;
                _input.clear();
                await ref
                    .read(docChatControllerProvider(widget.docId).notifier)
                    .send(text);
              },
              icon: const Icon(Icons.send),
              label: const Text('Send'),
            ),
          ],
        ),
      ],
    );
  }
}
