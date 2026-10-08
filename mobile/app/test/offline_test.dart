import 'package:argus_field/app/providers.dart';
import 'package:argus_field/app/queue.dart';
import 'package:argus_field/data/command_queue.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fake_server.dart';
import 'harness.dart';

ProviderContainer containerOf(Running app) =>
    ProviderScope.containerOf(app.tester.element(find.byType(MaterialApp)));

Future<void> reportOffline(Running app, {int photos = 1}) async {
  await app.go('/asset/$positionUid'); // online: the Position is saved on the device
  app.server.offline = true;
  await app.go('/report/$positionUid');
  await app.type('report-title', 'Gauge reads zero');
  await app.type('report-description', 'The gauge on the gun area reads zero since this morning.');
  await app.tap('when-now');
  for (var i = 0; i < photos; i++) {
    await app.tap('report-photo');
  }
  await app.tap('report-submit');
}

void main() {
  testWidgets('a report made offline is kept, shown as not yet in ARGUS, and sent ticket first when back (A64)',
      (tester) async {
    final app = await start(tester);
    await reportOffline(app);
    expect(find.byKey(const Key('ticket-pending')), findsOneWidget);
    expect(find.byKey(const Key('offline-banner')), findsOneWidget);
    final queue = containerOf(app).read(queueProvider.notifier);
    expect(queue.commands.map((c) => c.kind), ['ticket.create', 'attachment.upload']);
    expect(queue.commands.every((c) => c.open), isTrue);
    expect(app.server.sent('POST', '/v1/issues'), isEmpty);

    app.server.offline = false;
    await queue.sync(force: true);
    await tester.pumpAndSettle();
    final order = app.server.requests.where((r) => r.method != 'GET').map((r) => r.url.path).toList();
    expect(order.first, '/v1/issues'); // the ticket before its photo
    expect(order.where((p) => p.startsWith('/v1/uploads')), isNotEmpty);
    expect(queue.commands.every((c) => c.status == CommandStatus.accepted), isTrue);
    final create = app.server.requests.firstWhere((r) => r.method == 'POST' && r.url.path == '/v1/issues');
    expect(create.headers['X-ARGUS-Captured-At'], isNotNull);
    expect(create.headers['Idempotency-Key'], startsWith('ticket:'));
  });

  testWidgets('commands wait for what they depend on, whatever order they were made in (A64)', (tester) async {
    final app = await start(tester);
    final queue = containerOf(app).read(queueProvider.notifier);
    app.server.offline = true;
    final create = await queue.enqueue(kind: 'ticket.create', key: 'ticket:t1', target: 't1', label: 'Report', payload: {
      'uid': '11111111-1111-1111-1111-111111111111', 'title': 'Leak', 'description': '', 'asset_uid': positionUid});
    for (final n in [1, 2]) {
      await queue.enqueue(
          kind: 'ticket.comment', label: 'Comment $n', dependsOn: [create.id],
          payload: {'ticket_uid': '11111111-1111-1111-1111-111111111111', 'comment_uid': 'c$n', 'body': 'n$n'});
    }
    // The comments are older than the ticket in the queue: they still go after it.
    for (final c in queue.commands.where((c) => c.kind == 'ticket.comment')) {
      await CommandStore(containerOf(app).read(localStoreProvider)).save(c);
    }
    app.server.offline = false;
    await queue.sync(force: true);
    final posts = app.server.requests.where((r) => r.method == 'POST').map((r) => r.url.path).toList();
    expect(posts.indexOf('/v1/issues'), lessThan(posts.indexWhere((p) => p.endsWith('/comments'))));
  });

  testWidgets('a lost answer is retried with the same key (A63)', (tester) async {
    final app = await start(tester);
    final queue = containerOf(app).read(queueProvider.notifier);
    app.server.loseAnswer.add('POST /v1/issues/$ticketUid/comments');
    final c = await queue.enqueue(kind: 'ticket.comment', key: 'comment:k1', label: 'Comment',
        payload: {'ticket_uid': ticketUid, 'comment_uid': 'k1', 'body': 'hello'});
    await queue.sync(force: true);
    expect(queue.byId(c.id)!.status, CommandStatus.queued); // no answer: still pending
    await queue.sync(force: true);
    expect(queue.byId(c.id)!.status, CommandStatus.accepted);
    final keys = app.server.requests
        .where((r) => r.method == 'POST' && r.url.path.endsWith('/comments'))
        .map((r) => r.headers['Idempotency-Key'])
        .toList();
    expect(keys, ['comment:k1', 'comment:k1']);
  });

  testWidgets('a permission lost while offline ends as rejected, kept for the person (A62)', (tester) async {
    final app = await start(tester);
    final queue = containerOf(app).read(queueProvider.notifier);
    app.server.routes['POST /v1/issues/$ticketUid/comments'] = http.Response(
        '{"detail":"Not permitted","problem":{"code":"forbidden","error":"You may no longer change tickets here."}}', 403,
        headers: {'content-type': 'application/json'});
    final c = await queue.enqueue(kind: 'ticket.comment', label: 'Comment: pump replaced',
        payload: {'ticket_uid': ticketUid, 'comment_uid': 'k2', 'body': 'pump replaced'});
    await queue.sync(force: true);
    expect(queue.byId(c.id)!.status, CommandStatus.rejected);
    expect(queue.byId(c.id)!.lastCode, 'forbidden');
    await app.go('/outbox');
    expect(find.text('Comment: pump replaced'), findsOneWidget);
    expect(find.textContaining('You may no longer change tickets here'), findsOneWidget);
    expect(find.byKey(Key('outbox-retry-${c.id}')), findsNothing); // retrying cannot help
    await app.tap('outbox-discard-${c.id}');
    await app.tap('outbox-discard-ok');
    expect(queue.byId(c.id), isNull);
  });

  testWidgets('a command older than the retention expires without being sent (A65)', (tester) async {
    final app = await start(tester);
    final container = containerOf(app);
    final queue = container.read(queueProvider.notifier);
    final c = await queue.enqueue(kind: 'ticket.comment', label: 'Old comment',
        payload: {'ticket_uid': ticketUid, 'comment_uid': 'k3', 'body': 'old'});
    final old = PendingCommand.fromJson({...c.toJson(),
      'created_at': DateTime.now().subtract(const Duration(days: 9)).toUtc().toIso8601String()});
    await CommandStore(container.read(localStoreProvider)).save(old);
    container.invalidate(queueProvider);
    await container.read(queueProvider.future);
    await container.read(queueProvider.notifier).sync(force: true);
    expect(container.read(queueProvider.notifier).byId(c.id)!.status, CommandStatus.expired);
    expect(app.server.sent('POST', '/v1/issues/$ticketUid/comments'), isEmpty);
  });

  testWidgets('a record opened once is readable offline, labelled so', (tester) async {
    final app = await start(tester);
    await app.go('/asset/$positionUid');
    expect(find.text('GUNSIP01'), findsWidgets);
    app.server.offline = true;
    containerOf(app).invalidate(assetDetailProvider(positionUid));
    await app.go('/');
    await app.go('/asset/$positionUid');
    expect(find.text('GUNSIP01'), findsWidgets);
    expect(find.byKey(const Key('offline-banner')), findsOneWidget);
    // A search is never kept: offline, it says so.
    await app.go('/');
    await app.type('home-search', 'GUNSIP');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(find.text('No connection'), findsOneWidget);
  });

  testWidgets('a revoked device loses its copies and unsent changes, and the person is told (A71)', (tester) async {
    final app = await start(tester);
    await reportOffline(app, photos: 0);
    app.server.offline = false;
    app.server.override = FakeArgus.problem(401, 'revoked', error: 'This device was signed out of ARGUS.');
    await containerOf(app).read(queueProvider.notifier).sync(force: true);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('signin-token')), findsOneWidget);
    expect(find.textContaining('1 change(s) not yet sent were removed'), findsOneWidget);
    expect(find.textContaining('Report: Gauge reads zero'), findsOneWidget);
    final left = await const FlutterSecureStorage().readAll();
    expect(left.keys.where((k) => k.startsWith('argus.cache.') || k.startsWith('argus.queue.') ||
        k.startsWith('argus.blob.') || k == 'argus.session'), isEmpty);
  });

  testWidgets('signing out with unsent work asks first', (tester) async {
    final app = await start(tester);
    await reportOffline(app, photos: 0);
    await app.go('/');
    await app.tap('nav-menu');
    await tester.tap(find.text('Sign out'));
    await tester.pumpAndSettle();
    expect(find.text('Sign out and lose unsent changes?'), findsOneWidget);
    expect(find.textContaining('• Report: Gauge reads zero'), findsOneWidget);
  });
}
