import 'package:flutter/material.dart';
import '../../config.dart';
import 'chat_page.dart';

/// Test mode chat page that opens directly to a hardcoded document
class TestChatPage extends StatelessWidget {
  const TestChatPage({super.key});

  @override
  Widget build(BuildContext context) {
    if (!kTestMode) {
      // If not in test mode, redirect to normal chat
      return const ChatPage();
    }

    return ChatPage(docId: kTestDocId);
  }
}
