import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'app.dart';
import 'services/api_client.dart';

/// Global cipher used for all Hive boxes. Set once at startup.
HiveAesCipher? hiveCipher;

Future<HiveAesCipher> _getOrCreateHiveCipher() async {
  const storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  const cipherKey = 'hive_aes_key';

  try {
    String? existingKey = await storage.read(key: cipherKey);
    if (existingKey == null) {
      final key = Hive.generateSecureKey();
      await storage.write(key: cipherKey, value: base64UrlEncode(key));
      return HiveAesCipher(key);
    }
    final key = base64Url.decode(existingKey);
    return HiveAesCipher(key);
  } catch (e) {
    debugPrint('Secure storage read failed, resetting key: $e');
    try {
      await storage.delete(key: cipherKey);
    } catch (_) {}
    final key = Hive.generateSecureKey();
    try {
      await storage.write(key: cipherKey, value: base64UrlEncode(key));
    } catch (_) {}
    return HiveAesCipher(key);
  }
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive local storage
  await Hive.initFlutter();

  // Generate (or retrieve) the AES-256 cipher for all Hive boxes
  hiveCipher = await _getOrCreateHiveCipher();

  // Initialize singleton API client
  ApiClient().init();

  runApp(
    const ProviderScope(
      child: MyApp(),
    ),
  );
}
