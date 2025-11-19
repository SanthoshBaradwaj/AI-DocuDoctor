class ChatMessage {
  final String role; // "user" | "assistant"
  final String content;
  ChatMessage(this.role, this.content);

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}
