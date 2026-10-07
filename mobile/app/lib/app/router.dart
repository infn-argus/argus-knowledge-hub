import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/ask/ask_screen.dart';
import '../features/auth/signin_screen.dart';
import '../features/capture/register_screen.dart';
import '../features/installations/replace_screen.dart';
import '../features/review/review_screen.dart';
import '../features/sync/outbox_screen.dart';
import '../features/notifications/inbox_screen.dart';
import '../features/tickets/report_screen.dart';
import '../features/auth/update_screen.dart';
import '../features/auth/workspace_screen.dart';
import '../features/diagnostics/diagnostics_screen.dart';
import '../features/documents/document_screen.dart';
import '../features/documents/document_list_screen.dart';
import '../features/documents/document_write_screen.dart';
import '../features/tickets/ticket_edit_screen.dart';
import '../features/tickets/ticket_list_screen.dart';
import '../features/home/home_screen.dart';
import '../features/records/asset_edit_screen.dart';
import '../features/records/asset_screen.dart';
import '../features/records/resolve_screen.dart';
import '../features/scan/scan_screen.dart';
import '../features/tickets/ticket_screen.dart';
import 'providers.dart';

/// A place to return to after sign-in: only a path inside the app, never another origin.
String? safeReturn(String? from) {
  if (from == null || !from.startsWith('/') || from.startsWith('//')) return null;
  if (from.startsWith('/signin') || from.startsWith('/splash') || from.startsWith('/update')) return null;
  return from;
}

final _uid = RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$');
bool isUid(String s) => _uid.hasMatch(s);

/// Routes (flutter-app-design §7). The universal-link paths are the web's paths, so a link or a
/// label opens the same record in either client. Links other than /asset go through the server's
/// resolver, which also decides what this person may see (I-MOB-6).
final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => refresh.value++);
  ref.listen(updateRequiredProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  String? redirect(GoRouterState st) {
    final path = st.uri.path;
    final here = st.uri.toString();
    if (ref.read(updateRequiredProvider) != null) return path == '/update' ? null : '/update';

    final s = ref.read(sessionProvider);
    String withFrom(String to, String from) => '$to?from=${Uri.encodeComponent(from)}';
    final from = safeReturn(st.uri.queryParameters['from']);
    if (!s.hasValue && !s.hasError) return path == '/splash' ? null : withFrom('/splash', here);

    final session = s.value;
    if (session == null) {
      if (path == '/signin') return null;
      return withFrom('/signin', path == '/splash' ? (from ?? '/') : here);
    }
    if (session.workspaceId == null) {
      if (path == '/workspace') return null;
      return withFrom('/workspace', (path == '/splash' || path == '/signin') ? (from ?? '/') : here);
    }
    if (path == '/signin' || path == '/splash' || path == '/update') return from ?? '/';
    return null;
  }

  return GoRouter(
    initialLocation: '/',
    refreshListenable: refresh,
    debugLogDiagnostics: kDebugMode,
    redirect: (_, st) => redirect(st),
    routes: [
      GoRoute(path: '/splash', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/signin', builder: (_, _) => const SignInScreen()),
      GoRoute(path: '/update', builder: (_, _) => const UpdateScreen()),
      GoRoute(
          path: '/workspace',
          builder: (_, st) => WorkspaceScreen(returnTo: safeReturn(st.uri.queryParameters['from']))),
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(path: '/scan', builder: (_, st) => ScanScreen(pick: st.uri.queryParameters['pick'] == '1')),
      GoRoute(path: '/diagnostics', builder: (_, _) => const DiagnosticsScreen()),
      GoRoute(path: '/inbox', builder: (_, _) => const InboxScreen()),
      GoRoute(path: '/ask', builder: (_, _) => const AskScreen()),
      GoRoute(path: '/report/:uid', builder: (_, st) => ReportScreen(subjectUid: st.pathParameters['uid']!)),
      GoRoute(
          path: '/register',
          builder: (_, st) =>
              RegisterScreen(label: st.uri.queryParameters['label'], pick: st.uri.queryParameters['pick'] == '1')),
      GoRoute(path: '/replace/:uid', builder: (_, st) => ReplaceScreen(positionUid: st.pathParameters['uid']!)),
      GoRoute(path: '/reviews', builder: (_, _) => const ReviewScreen()),
      GoRoute(path: '/outbox', builder: (_, _) => const OutboxScreen()),
      GoRoute(path: '/asset/:uid', builder: (_, st) => AssetScreen(uid: st.pathParameters['uid']!)),
      GoRoute(path: '/asset/:uid/edit', builder: (_, st) => AssetEditScreen(uid: st.pathParameters['uid']!)),
      GoRoute(path: '/tickets', builder: (_, _) => const TicketListScreen()),
      GoRoute(path: '/ticket/:uid/edit', builder: (_, st) => TicketEditScreen(uid: st.pathParameters['uid']!)),
      GoRoute(path: '/documents', builder: (_, _) => const DocumentListScreen()),
      GoRoute(
          path: '/documents/new',
          builder: (_, st) => DocumentWriteScreen(assetUid: st.uri.queryParameters['asset'])),
      GoRoute(
          path: '/document/:uid/revision/:rev/edit',
          builder: (_, st) =>
              DocumentWriteScreen(documentUid: st.pathParameters['uid'], revisionUid: st.pathParameters['rev'])),
      // A document code or a Jira key in the link is resolved first; a uid opens directly.
      GoRoute(
          path: '/document/:id',
          builder: (_, st) => isUid(st.pathParameters['id']!)
              ? DocumentScreen(uid: st.pathParameters['id']!)
              : ResolveScreen(path: st.uri.path)),
      GoRoute(
          path: '/ticket/:id',
          builder: (_, st) => isUid(st.pathParameters['id']!)
              ? TicketScreen(uid: st.pathParameters['id']!)
              : ResolveScreen(path: st.uri.path)),
      for (final kind in const ['position', 'installation', 'review', 'lookup'])
        GoRoute(path: '/$kind/:id', builder: (_, st) => ResolveScreen(path: st.uri.path)),
    ],
  );
});
