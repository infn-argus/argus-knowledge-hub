/// Where this build talks to, set at build time (flutter-app-design §6):
/// `--dart-define=ARGUS_ENV=staging --dart-define=ARGUS_API_BASE=https://…` and so on,
/// or by the MDM's managed configuration in a later phase. Never typed by the user.
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.apiBase,
    required this.linkHost,
    required this.oidcIssuer,
    required this.oidcClientId,
    required this.oidcRedirect,
    required this.appVersion,
  });

  final String environment; // development | staging | production
  final String apiBase; // e.g. https://argus.example/ (no trailing /v1)
  final String linkHost; // the host of universal links and new QR labels
  final String oidcIssuer;
  final String oidcClientId;
  final String oidcRedirect;
  final String appVersion;

  bool get allowsDeveloperToken => environment != 'production';

  static AppConfig fromEnvironment() => const AppConfig(
        environment: String.fromEnvironment('ARGUS_ENV', defaultValue: 'development'),
        apiBase: String.fromEnvironment('ARGUS_API_BASE', defaultValue: 'http://localhost:8000'),
        linkHost: String.fromEnvironment('ARGUS_LINK_HOST', defaultValue: 'localhost'),
        oidcIssuer: String.fromEnvironment('OIDC_ISSUER', defaultValue: 'http://localhost:8081/realms/argus-dev'),
        oidcClientId: String.fromEnvironment('OIDC_CLIENT_ID', defaultValue: 'argus-mobile'),
        oidcRedirect: String.fromEnvironment('OIDC_REDIRECT', defaultValue: 'it.infn.argus.field:/oauthredirect'),
        appVersion: String.fromEnvironment('ARGUS_APP_VERSION', defaultValue: '0.1.0'),
      );
}
