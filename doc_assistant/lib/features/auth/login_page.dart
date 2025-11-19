import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/auth_state.dart';
// import '../../services/secure_storage_service.dart'; // use later for real token

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _emailCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  bool _busy = false;

  Future<void> _onLogin() async {
    setState(() => _busy = true);
    try {
      // TODO: call your backend /auth/login and get a token
      // await SecureStorageService.write('token', tokenFromServer);

      // For now, mark logged in in memory:
      authState.setLoggedIn(true);

      if (mounted) context.go('/home');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Login failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        minimum: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Spacer(),
            const Text('Welcome back 👋', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(
              controller: _emailCtrl,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _pwdCtrl,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _busy ? null : _onLogin,
              child: Text(_busy ? 'Signing in...' : 'Login'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => context.go('/forgot'),
              child: const Text('Forgot password?'),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text("Don't have an account?"),
                TextButton(
                  onPressed: () => context.go('/signup'),
                  child: const Text('Sign up'),
                ),
              ],
            ),
            const Spacer(),
          ],
        ),
      ),
    );
  }
}
