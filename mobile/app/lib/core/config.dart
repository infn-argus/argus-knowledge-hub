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
    this.offlineRetentionDays = 7,
    this.distribution = 'local',
  });

  final String environment; // development | staging | production
  final String apiBase; // e.g. https://argus.example/ (no trailing /v1)
  final String linkHost; // the host of universal links and new QR labels
  final String oidcIssuer;
  final String oidcClientId;
  final String oidcRedirect;
  final String appVersion;

  /// Where this build was published: `github` (an APK on a GitHub release — the app looks for newer ones
  /// there), `play` (the store updates it), or `local` (a developer's build: no update check).
  final String distribution;

  /// The repository whose releases carry the APK, for the update check of a `github` build.
  static const releasesRepo = 'infn-argus/argus-knowledge-hub';

  /// How long saved copies and pending commands may live on the device (U22, proposed 7 days).
  final int offlineRetentionDays;

  Duration get offlineRetention => Duration(days: offlineRetentionDays);

  bool get allowsDeveloperToken => environment != 'production';

  /// Google as the identity provider (OIDC_ISSUER=https://accounts.google.com) rather than
  /// Keycloak: its access tokens are opaque, so the app sends the ID token instead, and it
  /// grants a refresh token on `access_type=offline` rather than the `offline_access` scope.
  bool get usesGoogle => Uri.tryParse(oidcIssuer)?.host == 'accounts.google.com';

  static AppConfig fromEnvironment() => const AppConfig(
        environment: String.fromEnvironment('ARGUS_ENV', defaultValue: 'development'),
        apiBase: String.fromEnvironment('ARGUS_API_BASE', defaultValue: 'http://localhost:8000'),
        linkHost: String.fromEnvironment('ARGUS_LINK_HOST', defaultValue: 'localhost'),
        oidcIssuer: String.fromEnvironment('OIDC_ISSUER', defaultValue: 'http://localhost:8081/realms/argus-dev'),
        oidcClientId: String.fromEnvironment('OIDC_CLIENT_ID', defaultValue: 'argus-mobile'),
        oidcRedirect: String.fromEnvironment('OIDC_REDIRECT', defaultValue: 'it.infn.argus.field:/oauthredirect'),
        appVersion: String.fromEnvironment('ARGUS_APP_VERSION', defaultValue: '0.1.0'),
        offlineRetentionDays: int.fromEnvironment('ARGUS_OFFLINE_RETENTION_DAYS', defaultValue: 7),
        distribution: String.fromEnvironment('ARGUS_DISTRIBUTION', defaultValue: 'local'),
      );
}
