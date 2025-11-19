import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../../services/api_client.dart';
import 'package:dio/dio.dart';
import 'chat_models.dart';

/// Global chat controller (no document context)
final chatControllerProvider =
    NotifierProvider<ChatController, List<ChatMessage>>(ChatController.new);

class ChatController extends Notifier<List<ChatMessage>> {
  final _uuid = const Uuid();
  @override
  List<ChatMessage> build() => [
        ChatMessage(
            id: _uuid.v4(),
            role: 'assistant',
            content: 'Hi! Ask me about your documents.'),
      ];

  Future<void> send(String text) async {
    if (text.trim().isEmpty) return;
    final userMsg =
        ChatMessage(id: _uuid.v4(), role: 'user', content: text.trim());
    state = [...state, userMsg];

    final client = ApiClient();
    try {
      final response = await client.chatGlobal(
        messages:
            state.map((m) => {'role': m.role, 'content': m.content}).toList(),
      );

      // Handle new ChatResponseOut format
      final reply = (response['reply'] ?? '').toString();
      final messages = response['messages'] as List<dynamic>?;

      if (messages != null) {
        // Use the full conversation from backend
        state = messages
            .map((m) => ChatMessage(
                  id: _uuid.v4(),
                  role: m['role'] as String,
                  content: m['content'] as String,
                ))
            .toList();
      } else {
        // Fallback: just add the reply
        final botMsg =
            ChatMessage(id: _uuid.v4(), role: 'assistant', content: reply);
        state = [...state, botMsg];
      }
    } on DioException catch (e) {
      state = [
        ...state,
        ChatMessage(
            id: _uuid.v4(),
            role: 'assistant',
            content: 'Chat error: ${e.message}')
      ];
    }
  }

  void clear() {
    state = [
      ChatMessage(
          id: _uuid.v4(),
          role: 'assistant',
          content: 'Cleared. How can I help?')
    ];
  }
}

/// Document-scoped chat controller
final docChatControllerProvider =
    NotifierProvider.family<DocChatController, List<ChatMessage>, int>(
  DocChatController.new,
);

class DocChatController extends FamilyNotifier<List<ChatMessage>, int> {
  final _uuid = const Uuid();

  @override
  List<ChatMessage> build(int docId) {
    return [
      ChatMessage(
          id: _uuid.v4(),
          role: 'assistant',
          content: 'You are chatting about document #$docId.'),
    ];
  }

  Future<void> send(String text) async {
    if (text.trim().isEmpty) return;
    final docId = arg;
    final userMsg =
        ChatMessage(id: _uuid.v4(), role: 'user', content: text.trim());
    state = [...state, userMsg];

    final client = ApiClient();
    try {
      final response = await client.chatWithDocument(
        docId: docId,
        messages:
            state.map((m) => {'role': m.role, 'content': m.content}).toList(),
      );

      // Handle new ChatResponseOut format
      final reply = (response['reply'] ?? '').toString();
      final messages = response['messages'] as List<dynamic>?;

      if (messages != null) {
        // Use the full conversation from backend
        state = messages
            .map((m) => ChatMessage(
                  id: _uuid.v4(),
                  role: m['role'] as String,
                  content: m['content'] as String,
                ))
            .toList();
      } else {
        // Fallback: just add the reply
        final botMsg =
            ChatMessage(id: _uuid.v4(), role: 'assistant', content: reply);
        state = [...state, botMsg];
      }
    } on DioException catch (e) {
      state = [
        ...state,
        ChatMessage(
            id: _uuid.v4(),
            role: 'assistant',
            content: 'Chat error: ${e.message}')
      ];
    }
  }

  void clear() {
    final docId = arg;
    state = [
      ChatMessage(
          id: _uuid.v4(),
          role: 'assistant',
          content: 'Cleared. How can I help with document #$docId?')
    ];
  }
}
