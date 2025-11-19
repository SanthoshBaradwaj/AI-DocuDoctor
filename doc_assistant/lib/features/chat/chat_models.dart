class ChatMessage {
  final String id;
  final String role; // 'user' | 'assistant'
  final String content;
  ChatMessage({required this.id, required this.role, required this.content});
}
