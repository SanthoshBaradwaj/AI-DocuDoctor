/// App-wide configuration. You can wire these from env/flavors later.
class AppConfig {
  /// Default webhook URL (leave empty to set in UI on Webhook page)
  static String defaultWebhookUrl = '';

  /// Example API base; change when you add a real backend
  static const String apiBaseUrl = 'https://example.com/api';
}
