import 'package:shared_preferences/shared_preferences.dart';

class Session {
  static const _kLoggedIn = 'logged_in';
  static const _kToken = 'auth_token';

  static Future<bool> isLoggedIn() async {
    final sp = await SharedPreferences.getInstance();
    return sp.getBool(_kLoggedIn) ?? false;
  }

  static Future<void> setLoggedIn(bool v) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool(_kLoggedIn, v);
  }

  static Future<void> saveToken(String token) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setString(_kToken, token);
  }

  static Future<String?> token() async {
    final sp = await SharedPreferences.getInstance();
    return sp.getString(_kToken);
  }

  static Future<void> logout() async {
    final sp = await SharedPreferences.getInstance();
    await sp.remove(_kLoggedIn);
    await sp.remove(_kToken);
  }
}
