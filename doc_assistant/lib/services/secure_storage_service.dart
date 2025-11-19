import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Simple wrapper for secure-ish key/value storage.
class SecureStorageService {
  static final FlutterSecureStorage _secure = const FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      resetOnError: true,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock,
    ),
    mOptions: MacOsOptions(
      accessibility: KeychainAccessibility.first_unlock,
    ),
  );

  static Future<void> write(String key, String value) async {
    if (_useSecure()) {
      await _secure.write(key: key, value: value);
    } else {
      final sp = await SharedPreferences.getInstance();
      await sp.setString(key, value);
    }
  }

  static Future<String?> read(String key) async {
    if (_useSecure()) {
      return _secure.read(key: key);
    } else {
      final sp = await SharedPreferences.getInstance();
      return sp.getString(key);
    }
  }

  static Future<void> delete(String key) async {
    if (_useSecure()) {
      await _secure.delete(key: key);
    } else {
      final sp = await SharedPreferences.getInstance();
      await sp.remove(key);
    }
  }

  static bool _useSecure() {
    if (kIsWeb) return false;
    try {
      return Platform.isAndroid || Platform.isIOS || Platform.isMacOS;
    } catch (_) {
      return false;
    }
  }
}
