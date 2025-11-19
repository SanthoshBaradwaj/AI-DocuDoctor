class ChatMessage {
  final String role; // "user" | "assistant"
  final String content;
  ChatMessage(this.role, this.content);

  Map<String, dynamic> toJson() => {'role': role, 'content': content};

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      json['role'] as String,
      json['content'] as String,
    );
  }
}

class ChatResponse {
  final String reply;
  final List<ChatMessage> messages;

  ChatResponse({
    required this.reply,
    required this.messages,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      reply: json['reply'] as String? ?? '',
      messages: (json['messages'] as List<dynamic>?)
              ?.map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}
