import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/widgets/app_scaffold.dart';
import '../../theme/widgets/app_button.dart';
import 'chat_controller.dart';
import 'chat_models.dart';

class ChatPage extends ConsumerStatefulWidget {
  final int? docId; // Optional document ID for document-scoped chat
  const ChatPage({super.key, this.docId});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Use document-scoped chat if docId is provided, otherwise global chat
    final messages = widget.docId != null
        ? ref.watch(docChatControllerProvider(widget.docId!))
        : ref.watch(chatControllerProvider);
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    return AppScaffold(
      title:
          widget.docId != null ? 'Chat - Document #${widget.docId}' : 'AI Chat',
      body: Column(
        children: [
          // Make list take remaining height and keep padding at bottom when keyboard shows
          Expanded(
            child: ListView.separated(
              padding: EdgeInsets.only(bottom: bottom + 12),
              itemCount: messages.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, i) => _Bubble(msg: messages[i]),
            ),
          ),
          const SizedBox(height: 8),
          // Keep input above keyboard
          Padding(
            padding: EdgeInsets.only(bottom: bottom > 0 ? bottom : 0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    decoration:
                        const InputDecoration(hintText: 'Type a message...'),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                AppButton(label: 'Send', icon: Icons.send, onPressed: _send),
                const SizedBox(width: 8),
                AppButton(
                  label: 'Clear',
                  icon: Icons.clear_all,
                  onPressed: () {
                    if (widget.docId != null) {
                      ref
                          .read(
                              docChatControllerProvider(widget.docId!).notifier)
                          .clear();
                    } else {
                      ref.read(chatControllerProvider.notifier).clear();
                    }
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _send() async {
    final text = _input.text;
    if (text.trim().isEmpty) return;
    _input.clear();

    if (widget.docId != null) {
      await ref
          .read(docChatControllerProvider(widget.docId!).notifier)
          .send(text);
    } else {
      await ref.read(chatControllerProvider.notifier).send(text);
    }
  }
}

class _Bubble extends StatelessWidget {
  final ChatMessage msg;
  const _Bubble({required this.msg});

  @override
  Widget build(BuildContext context) {
    final isUser = msg.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 600),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        margin: const EdgeInsets.symmetric(horizontal: 6),
        decoration: BoxDecoration(
          color: isUser
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).cardColor,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(14),
            topRight: const Radius.circular(14),
            bottomLeft: Radius.circular(isUser ? 14 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 14),
          ),
        ),
        child: Text(
          msg.content,
          style: TextStyle(color: isUser ? Colors.white : null),
        ),
      ),
    );
  }
}
