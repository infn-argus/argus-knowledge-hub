import 'package:argus_field/app/app.dart';
import 'package:argus_field/app/providers.dart';
import 'package:argus_field/core/blob_store.dart';
import 'package:argus_field/core/local_store.dart';
import 'package:argus_field/app/router.dart';
import 'package:argus_field/core/config.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fake_server.dart';

const _config = AppConfig(
  environment: 'development',
  apiBase: 'https://argus.test',
  linkHost: 'argus.test',
  oidcIssuer: '',
  oidcClientId: '',
  oidcRedirect: '',
  appVersion: '0.1.0',
);

Future<FakeArgus> _start(WidgetTester tester, {Map<String, String> stored = const {}}) async {
  FlutterSecureStorage.setMockInitialValues(Map.of(stored));
  await tester.binding.setSurfaceSize(const Size(420, 900));
  final server = FakeArgus();
  await tester.pumpWidget(ProviderScope(
    retry: retryPolicy,
    overrides: [
      configProvider.overrideWithValue(_config),
      httpClientProvider.overrideWithValue(server.client),
      cacheStoreProvider.overrideWithValue(MemoryLocalStore()),
      blobStoreProvider.overrideWithValue(MemoryBlobStore()),
    ],
    child: const ArgusFieldApp(),
  ));
  await tester.pumpAndSettle();
  return server;
}

const _signedIn = {
  'argus.session': '{"accessToken":"tok","authType":"token","workspaceId":"$workspaceId",'
      '"workspaceName":"Slice","deviceId":"dev-1"}',
};

void main() {
  testWidgets('sign in with a token, choose a workspace, search and open a Position', (tester) async {
    final server = await _start(tester);
    expect(find.text('ARGUS Field'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('signin-token')), 'tok');
    await tester.tap(find.byKey(const Key('signin-token-submit')));
    await tester.pumpAndSettle();
    // The device was registered while signing in.
    expect(server.requests.any((r) => r.method == 'POST' && r.url.path == '/v1/devices'), isTrue);

    await tester.tap(find.byKey(const Key('workspace-$workspaceId')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('home-search')), findsOneWidget);

    await tester.enterText(find.byKey(const Key('home-search')), 'GUNSIP');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(find.text('S7C415E:POS:GUNSIP02 · GUNSIP02'), findsOneWidget);
    expect(server.requests.last.headers['X-Workspace-Id'], workspaceId);
  });

  testWidgets('a Position link opens the Position with what is installed there', (tester) async {
    await _start(tester, stored: _signedIn);
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/position/$positionUid');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('asset-name')), findsOneWidget);
    // Shown twice now: the app bar's title is the name, not the key (it used to be the key).
    expect(find.text('GUNSIP01'), findsWidgets);
    expect(find.text('Position'), findsOneWidget);
    expect(find.text('INSTALLED HERE NOW'), findsOneWidget);
    expect(find.text('S7C415EINV-84321 · Ion pump 84321'), findsOneWidget);
    expect(find.text('Pressure spike on gun ion pump'), findsOneWidget);
  });

  testWidgets('a draft document says not to work from it', (tester) async {
    await _start(tester, stored: _signedIn);
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/document/$draftUid');
    await tester.pumpAndSettle();
    expect(find.textContaining('No current revision'), findsOneWidget);
    router.go('/document/$documentUid');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('doc-title')), findsOneWidget);
    expect(find.textContaining('Do not work from'), findsNothing);
  });

  testWidgets('a revoked device is signed out and its session removed', (tester) async {
    final server = await _start(tester, stored: _signedIn);
    server.override = FakeArgus.problem(401, 'revoked');
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/ticket/$ticketUid');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('signin-token')), findsOneWidget);
    expect(find.textContaining('signed out of ARGUS by an administrator'), findsOneWidget);
    expect(await const FlutterSecureStorage().read(key: 'argus.session'), isNull);
  });

  testWidgets('a client too old is stopped at the update screen', (tester) async {
    final server = await _start(tester, stored: _signedIn);
    server.override = FakeArgus.problem(426, 'client_too_old', minimum: '1.4.0');
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/ticket/$ticketUid');
    await tester.pumpAndSettle();
    expect(find.text('Update required'), findsOneWidget);
    expect(find.textContaining('1.4.0'), findsOneWidget);
  });

  testWidgets('a label nobody can see is asked for once and shown as not found', (tester) async {
    final server = await _start(tester, stored: _signedIn);
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/lookup/NOPE-404');
    await tester.pumpAndSettle(const Duration(seconds: 5));
    expect(find.text('Not found'), findsOneWidget);
    expect(server.requests.where((r) => r.url.path == '/v1/links/resolve'), hasLength(1));
  });

  testWidgets('a serial held by two units opens neither and offers both', (tester) async {
    final server = await _start(tester, stored: _signedIn);
    server.override = http.Response(
        '{"detail":{"error":"This label matches more than one record.","code":"ambiguous","candidates":['
        '{"uid":"u1","key":"IP-1","name":"Pump A","type":"Ion Pump","attributes":{"serial":"123"}},'
        '{"uid":"u2","key":"IP-2","name":"Pump B","type":"Ion Pump","attributes":{"serial":"123"}}]}}',
        409);
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/lookup/123');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('candidate-u1')), findsOneWidget);
    expect(find.byKey(const Key('candidate-u2')), findsOneWidget);
    expect(find.byKey(const Key('asset-name')), findsNothing);
    expect(server.requests.where((r) => r.url.path.startsWith('/v1/assets/')), isEmpty);
  });

  testWidgets('a link opened while signed out survives the sign-in', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    final server = await _start(tester);
    final router = ProviderScope.containerOf(tester.element(find.byType(ArgusFieldApp))).read(routerProvider);
    router.go('/ticket/$ticketUid');
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('signin-token')), 'tok');
    await tester.tap(find.byKey(const Key('signin-token-submit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('workspace-$workspaceId')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('ticket-title')), findsOneWidget);
    expect(server.requests.any((r) => r.url.path == '/v1/issues/$ticketUid'), isTrue);
  });
}
