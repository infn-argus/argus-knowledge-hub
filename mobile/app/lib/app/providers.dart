import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../core/config.dart';
import '../core/problem.dart';
import '../core/session.dart';
import '../data/api_service.dart';
import '../data/repositories.dart';
import '../domain/models.dart';
import '../features/auth/auth_service.dart';

/// Riverpod retries a failed provider by default. A refusal (not found, forbidden, invalid,
/// revoked) will not change by asking again, so only an unreachable server is retried, briefly.
Duration? retryPolicy(int retryCount, Object error) {
  if (error is! Problem || error.code != ProblemCode.offline || retryCount >= 3) return null;
  return Duration(milliseconds: 500 * (1 << retryCount));
}

final configProvider = Provider<AppConfig>((_) => AppConfig.fromEnvironment());
/// The HTTP transport. `null` is the platform default; tests put a fake server here.
final httpClientProvider = Provider<http.Client?>((_) => null);

final sessionStoreProvider = Provider<SessionStore>((_) => SessionStore());
final authenticatorProvider = Provider<Authenticator>((ref) => AppAuthAuthenticator(ref.watch(configProvider)));

/// Set when the server says this version is too old (426 `client_too_old`). Nothing else works
/// until the app is updated (revision §24.2, I-MOB-7).
class UpdateRequired extends Notifier<String?> {
  @override
  String? build() => null;
  void require(String minimum) => state = minimum;
}

final updateRequiredProvider = NotifierProvider<UpdateRequired, String?>(UpdateRequired.new);

/// Why the last session ended, shown once on the sign-in screen.
class SignOutReason extends Notifier<String?> {
  @override
  String? build() => null;
  void set(String? reason) => state = reason;
}

final signOutReasonProvider = NotifierProvider<SignOutReason, String?>(SignOutReason.new);

/// The signed-in session. `null` means signed out.
class SessionController extends AsyncNotifier<Session?> {
  SessionStore get _store => ref.read(sessionStoreProvider);
  Future<Session?>? _refreshing;

  @override
  Future<Session?> build() async {
    try {
      return await _store.load();
    } catch (_) {
      return null;
    }
  }

  Session? get current => state.value;

  Future<void> _set(Session? s) async {
    if (s == null) {
      await _store.wipe();
    } else {
      await _store.save(s);
    }
    state = AsyncData(s);
  }

  /// Sign in with a token (development and web builds only).
  Future<void> signInWithToken(String token) async {
    if (!ref.read(configProvider).allowsDeveloperToken) {
      throw Problem(ProblemCode.forbidden, 'Tokens are not accepted by this build.');
    }
    await _finishSignIn(Session(accessToken: token.trim(), authType: 'token'));
  }

  Future<void> signInWithOidc() async {
    final s = await ref.read(authenticatorProvider).signInWithOidc();
    await _finishSignIn(s);
  }

  /// Check the credentials against ARGUS and register this device before anything is kept.
  Future<void> _finishSignIn(Session candidate) async {
    final config = ref.read(configProvider);
    final service = ApiService(config, () => candidate, httpClient: ref.read(httpClientProvider));
    final label = await WorkspaceRepository(service).whoAmI();
    final installation = await _store.installationId();
    final device = await DeviceRepository(service).register(installation, config.appVersion);
    ref.read(signOutReasonProvider.notifier).set(null);
    await _set(candidate.copyWith(deviceId: device, userLabel: label));
  }

  Future<void> chooseWorkspace(WorkspaceChoice w) async {
    final s = current;
    if (s == null) return;
    await _set(s.copyWith(workspaceId: w.id, workspaceName: w.name));
  }

  Future<void> signOut({String? reason}) async {
    final s = current;
    if (s != null) await ref.read(authenticatorProvider).endSession(s);
    ref.read(signOutReasonProvider.notifier).set(reason);
    await _set(null);
  }

  /// Refresh an OIDC access token shortly before it expires; on failure the person signs in again.
  Future<void> ensureFresh() async {
    final s = current;
    if (s == null || !s.expired || s.authType != 'oidc') return;
    _refreshing ??= ref.read(authenticatorProvider).refresh(s);
    final fresh = await _refreshing;
    _refreshing = null;
    if (fresh == null) {
      await signOut(reason: 'Your session expired. Sign in again.');
    } else {
      await _set(fresh);
    }
  }

  /// Problems that end the session, whatever screen met them.
  void onProblem(Problem p) {
    switch (p.code) {
      case ProblemCode.revoked:
        signOut(reason: 'This device was signed out of ARGUS by an administrator. Its local data was removed.');
      case ProblemCode.unauthenticated:
        signOut(reason: 'Your session is no longer valid. Sign in again.');
      case ProblemCode.clientTooOld:
        ref.read(updateRequiredProvider.notifier).require(p.minimum ?? 'a newer version');
      default:
        break;
    }
  }
}

final sessionProvider = AsyncNotifierProvider<SessionController, Session?>(SessionController.new);

final apiServiceProvider = Provider<ApiService>((ref) {
  final controller = ref.read(sessionProvider.notifier);
  return ApiService(
    ref.watch(configProvider),
    () => ref.read(sessionProvider).value,
    onProblem: controller.onProblem,
    ensureFresh: controller.ensureFresh,
    httpClient: ref.watch(httpClientProvider),
  );
});

final workspaceRepositoryProvider = Provider((ref) => WorkspaceRepository(ref.watch(apiServiceProvider)));
final lookupRepositoryProvider = Provider((ref) => LookupRepository(ref.watch(apiServiceProvider)));
final assetRepositoryProvider = Provider((ref) => AssetRepository(ref.watch(apiServiceProvider)));
final ticketRepositoryProvider = Provider((ref) => TicketRepository(ref.watch(apiServiceProvider)));
final documentRepositoryProvider = Provider((ref) => DocumentRepository(ref.watch(apiServiceProvider)));

/// The workspace in use: every record read below is keyed by it, so switching reloads everything.
final workspaceIdProvider = Provider<String?>((ref) => ref.watch(sessionProvider).value?.workspaceId);

final myWorkspacesProvider = FutureProvider.autoDispose<List<WorkspaceChoice>>(
    (ref) => ref.watch(workspaceRepositoryProvider).mine());

final assetDetailProvider = FutureProvider.autoDispose.family<AssetDetail, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(assetRepositoryProvider).detail(uid);
});

final ticketDetailProvider = FutureProvider.autoDispose.family<TicketDetail, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(ticketRepositoryProvider).detail(uid);
});

final documentDetailProvider = FutureProvider.autoDispose.family<DocumentDetail, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(documentRepositoryProvider).detail(uid);
});

final resolveProvider = FutureProvider.autoDispose.family<LinkTarget, String>((ref, path) {
  ref.watch(workspaceIdProvider);
  return ref.watch(lookupRepositoryProvider).resolveLink(path);
});

final searchProvider = FutureProvider.autoDispose.family<SearchResults, String>((ref, q) {
  ref.watch(workspaceIdProvider);
  if (q.trim().length < 2) return Future.value(const SearchResults());
  return ref.watch(lookupRepositoryProvider).search(q.trim());
});

final serverMetaProvider = FutureProvider.autoDispose<Map<String, Object?>>((ref) async {
  final api = ref.watch(apiServiceProvider);
  final meta = await api.json((c) => api.meta(c).apiMetaWithHttpInfo());
  return meta is Map ? meta.map((k, v) => MapEntry(k.toString(), v)) : {'value': meta};
});
