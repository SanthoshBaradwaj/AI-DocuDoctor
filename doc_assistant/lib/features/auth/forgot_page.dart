import 'package:flutter/material.dart';

class ForgotPage extends StatefulWidget {
  const ForgotPage({super.key});
  @override State<ForgotPage> createState() => _ForgotPageState();
}

class _ForgotPageState extends State<ForgotPage> {
  final _email = TextEditingController();
  bool _sent = false;

  Future<void> _send() async {
    await Future.delayed(const Duration(milliseconds: 400));
    setState(() => _sent = true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset password')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(children: [
          TextField(controller: _email, decoration: const InputDecoration(labelText: 'Account email')),
          const SizedBox(height: 12),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: _send, child: const Text('Send reset link'))),
          const SizedBox(height: 12),
          if (_sent) const Text('If that email exists, a reset link was sent.'),
        ]),
      ),
    );
  }
}
