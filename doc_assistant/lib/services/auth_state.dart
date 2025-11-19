import 'package:flutter/foundation.dart';

/// Super simple in-memory auth flag that GoRouter can listen to.
/// In real life, read/write a token via SecureStorageService and call setLoggedIn.
class AuthState extends ChangeNotifier {
  bool _loggedIn = false;

  bool get isLoggedIn => _loggedIn;

  void setLoggedIn(bool value) {
    if (_loggedIn != value) {
      _loggedIn = value;
      notifyListeners();
    }
  }
}

// Global singleton for quick wiring.
// (You can move this to a proper DI or Riverpod later.)
final authState = AuthState();
