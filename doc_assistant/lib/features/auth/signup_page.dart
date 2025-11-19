import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/session.dart';

class SignupPage extends StatefulWidget {
  const SignupPage({super.key});
  @override State<SignupPage> createState() => _SignupPageState();
}

class _SignupPageState extends State<SignupPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _busy = false;
  String? _err;

  Future<void> _signup() async {
    setState(() { _busy = true; _err = null; });
    await Future.delayed(const Duration(milliseconds: 300));
    if (_email.text.trim().isEmpty || _password.text.length < 6) {
      setState(() { _busy = false; _err = 'Enter a valid email & 6+ char password'; });
      return;
    }
    if (_password.text != _confirm.text) {
      setState(() { _busy = false; _err = 'Passwords do not match'; });
      return;
    }
    await Session.setLoggedIn(true); // stub for now
    if (!mounted) return;
    context.go('/');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: _email, decoration: const InputDecoration(labelText: 'Email')),
              const SizedBox(height: 12),
              TextField(controller: _password, decoration: const InputDecoration(labelText: 'Password'), obscureText: true),
              const SizedBox(height: 12),
              TextField(controller: _confirm, decoration: const InputDecoration(labelText: 'Confirm password'), obscureText: true, onSubmitted: (_) => _signup()),
              if (_err != null) ...[
                const SizedBox(height: 8), Text(_err!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: FilledButton(onPressed: _busy ? null : _signup, child: Text(_busy ? 'Creating…' : 'Create account'))),
            ]),
          ),
        ),
      ),
    );
  }
}
