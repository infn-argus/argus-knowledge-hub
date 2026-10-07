import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../core/local_store.dart';
import '../data/caching_client.dart';

import '../core/config.dart';
import '../core/problem.dart';
import '../core/session.dart';
import '../data/api_service.dart';
import '../data/ask_repository.dart';
import '../data/capture_repositories.dart';
import '../data/replacement_repositories.dart';
import '../data/repositories.dart';
import '../domain/capture.dart';
import '../domain/models.dart';
import '../features/ask/voice.dart';
import '../features/auth/auth_service.dart';
import '../features/capture/photo_source.dart';
import 'queue.dart';

/// Riverpod retries a failed provider by default. A refusal (not found, forbidden, invalid,
/// revoked) will not change by asking again, so only an unreachable server is retried, briefly.
Duration? retryPolicy(int retryCount, Object error) {
  if (error is! Problem || error.code != ProblemCode.offline || retryCount >= 3) return null;
  return Duration(milliseconds: 500 * (1 << retryCount));
}

final configProvider = Provider<AppConfig>((_) => AppConfig.fromEnvironment());
/// The HTTP transport. `null` is the platform default; tests put a fake server here.
final httpClientProvider = Provider<http.Client?>((_) => null);

/// Saved copies, pending commands and their attachments, encrypted on the device.
final localStoreProvider = Provider<LocalStore>((_) => SecureLocalStore());

/// Whether ARGUS answered the last request, and the device's offset from the server's clock.
class Reachability {
  const Reachability({this.reachable = true, this.serverOffset = Duration.zero, this.since});

  final bool reachable;
  final Duration serverOffset; // server time minus device time
  final DateTime? since;

  DateTime serverNow() => DateTime.now().add(serverOffset);
}

class ReachabilityController extends Notifier<Reachability> {
  @override
  Reachability build() => const Reachability();

  void reached(bool ok) {
    if (ok != state.reachable) {
      state = Reachability(reachable: ok, serverOffset: state.serverOffset, since: DateTime.now());
    }
  }

  void serverTime(DateTime serverNow) {
    final offset = serverNow.difference(DateTime.now());
    // The Date header has a one-second resolution: only a real change is worth a rebuild.
    if ((offset - state.serverOffset).abs() > const Duration(seconds: 5)) {
      state = Reachability(reachable: state.reachable, serverOffset: offset, since: state.since);
    }
  }
}

final reachabilityProvider = NotifierProvider<ReachabilityController, Reachability>(ReachabilityController.new);

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
    // Already signed out: a later refusal (several requests in flight) must not replace what the
    // person was told first.
    if (s == null) return;
    await ref.read(authenticatorProvider).endSession(s);
    // Everything the app keeps goes with the session (§5.6, A71). Pending work is not lost silently:
    // the person is told what was not sent.
    final lost = ref.exists(queueProvider) ? ref.read(queueProvider.notifier).unsent : const [];
    final told = lost.isEmpty
        ? reason
        : '${reason ?? 'Signed out.'} ${lost.length} change(s) not yet sent were removed from this device: '
            '${lost.take(5).map((c) => c.label).join('; ')}${lost.length > 5 ? '; …' : ''}.';
    ref.read(signOutReasonProvider.notifier).set(told);
    await _set(null);
    ref.invalidate(queueProvider);
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
  final config = ref.watch(configProvider);
  final reach = ref.read(reachabilityProvider.notifier);
  final caching = CachingClient(
    ref.watch(httpClientProvider) ?? http.Client(),
    ref.watch(localStoreProvider),
    retention: config.offlineRetention,
    scope: () {
      final s = ref.read(sessionProvider).value;
      return '${s?.workspaceId}|${s?.userLabel ?? s?.deviceId}';
    },
    onReachable: (ok) => Future.microtask(() => reach.reached(ok)),
    onServerTime: (t) => Future.microtask(() => reach.serverTime(t)),
  );
  return ApiService(
    config,
    () => ref.read(sessionProvider).value,
    onProblem: controller.onProblem,
    ensureFresh: controller.ensureFresh,
    httpClient: caching,
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

/// A reference attribute's target, named — null if it can no longer be resolved (deleted, or not
/// visible to this viewer), so the caller falls back to showing the bare uid rather than crashing.
final assetBriefProvider = FutureProvider.autoDispose.family<RecordBrief?, String>((ref, uid) async {
  ref.watch(workspaceIdProvider);
  try {
    return await ref.watch(assetRepositoryProvider).brief(uid);
  } on Problem {
    return null;
  }
});

final assetCommentsProvider = FutureProvider.autoDispose.family<List<Comment>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(assetRepositoryProvider).comments(uid);
});

final assetHistoryProvider = FutureProvider.autoDispose.family<List<HistoryEntry>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(assetRepositoryProvider).history(uid);
});

final assetAttachmentsProvider = FutureProvider.autoDispose.family<List<AttachmentInfo>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(assetRepositoryProvider).attachments(uid);
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

// --------------------------------------------------------------------------- capture and tickets (M2)

final photoSourceProvider = Provider<PhotoSource>((_) => DevicePhotoSource());
final intakeRepositoryProvider = Provider((ref) => IntakeRepository(ref.watch(apiServiceProvider)));
final schemaRepositoryProvider = Provider((ref) => SchemaRepository(ref.watch(apiServiceProvider)));
final uploadRepositoryProvider = Provider((ref) => UploadRepository(ref.watch(apiServiceProvider)));
final ticketCommandsProvider = Provider((ref) => TicketCommands(ref.watch(apiServiceProvider)));
final equipmentCommandsProvider = Provider((ref) => EquipmentCommands(ref.watch(apiServiceProvider)));
final notificationRepositoryProvider = Provider((ref) => NotificationRepository(ref.watch(apiServiceProvider)));

final ticketKindsProvider = FutureProvider.autoDispose<List<TicketKind>>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(schemaRepositoryProvider).ticketKinds();
});

final objectTypesProvider = FutureProvider.autoDispose<List<EquipmentType>>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(schemaRepositoryProvider).objectTypes();
});

final schemaAttributesProvider = FutureProvider.autoDispose.family<List<AttributeDef>, String>((ref, schemaUid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(schemaRepositoryProvider).effectiveAttributes(schemaUid);
});

/// Candidates for a reference attribute's picker: every asset of [schemaUid], plus its descendant
/// types when [includeChildren] — mirrors the web form's ReferenceInput.
final referenceCandidatesProvider =
    FutureProvider.autoDispose.family<List<RecordBrief>, (String schemaUid, bool includeChildren)>((ref, key) async {
  ref.watch(workspaceIdProvider);
  final (schemaUid, includeChildren) = key;
  final assets = ref.watch(assetRepositoryProvider);
  if (!includeChildren) return assets.listByType(schemaUid);
  final allowed = await ref.watch(schemaRepositoryProvider).descendantSchemaUids(schemaUid);
  final all = await assets.listByType(null);
  return all.where((a) => allowed.contains(a.schemaUid)).toList();
});

final commentsProvider = FutureProvider.autoDispose.family<List<Comment>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(ticketCommandsProvider).comments(uid);
});

final attachmentsProvider = FutureProvider.autoDispose.family<List<AttachmentInfo>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(ticketCommandsProvider).attachments(uid);
});

final transitionsProvider = FutureProvider.autoDispose.family<List<TransitionOption>, String>((ref, uid) {
  ref.watch(workspaceIdProvider);
  return ref.watch(ticketCommandsProvider).transitions(uid);
});

/// The inbox. Push is decision U21; until then the app asks when it opens and when the person looks.
final notificationsProvider = FutureProvider.autoDispose<List<NotificationItem>>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(notificationRepositoryProvider).mine();
});

// --------------------------------------------------------------------------- replacement and review (M3)

final replacementRepositoryProvider = Provider((ref) => ReplacementRepository(ref.watch(apiServiceProvider)));
final reviewRepositoryProvider = Provider((ref) => ReviewRepository(ref.watch(apiServiceProvider)));

final myReviewItemsProvider = FutureProvider.autoDispose<List<ReviewItem>>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(reviewRepositoryProvider).mine();
});

// --------------------------------------------------------------------------- ask

final askRepositoryProvider = Provider((ref) => AskRepository(ref.watch(apiServiceProvider)));

/// The phone's speech recognition and voice. Tests put a fake here.
final voiceProvider = Provider<Voice>((_) => DeviceVoice());

final askAvailabilityProvider = FutureProvider.autoDispose<AskAvailability>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(askRepositoryProvider).availability();
});

final askConversationsProvider = FutureProvider.autoDispose<List<AskConversationSummary>>((ref) {
  ref.watch(workspaceIdProvider);
  return ref.watch(askRepositoryProvider).conversations();
});
