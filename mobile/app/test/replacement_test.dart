import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

Future<void> scanTyped(Running app, String label) async {
  await app.tester.enterText(find.byKey(const Key('scan-typed')), label);
  await app.tester.testTextInput.receiveAction(TextInputAction.go);
  await app.tester.pumpAndSettle();
}

void main() {
  testWidgets('a like-for-like replacement is checked, then applied in one command', (tester) async {
    final app = await start(tester);
    await app.go('/asset/$positionUid');
    await app.tap('asset-replace');
    expect(find.text('S7C415EINV-84321 · Ion pump 84321'), findsOneWidget);

    await app.tap('scan-incoming');
    await scanTyped(app, 'IP-NEW-1');
    expect(find.text('Ion pump gun area 2'), findsOneWidget);
    await app.tap('replace-photo');
    await app.tap('replace-check');
    expect(find.textContaining('Ready: the old Installation ends'), findsOneWidget);
    final [dry] = app.server.sent('POST', '/v1/installations/replace');
    expect(dry['dry_run'], isTrue);
    expect(dry['outgoing_uid'], recordedUnit);
    expect(dry['seen_installation_uid'], recordedInstallation);
    expect(dry['incoming_uid'], incomingUnit);

    await app.tap('replace-submit');
    expect(find.byKey(const Key('replace-done')), findsOneWidget);
    expect(find.text('Replaced'), findsOneWidget);
    final submit = app.server.requests.lastWhere((r) => r.url.path == '/v1/installations/replace');
    expect(jsonDecode(submit.body)['dry_run'], isFalse);
    expect(submit.headers['Idempotency-Key'], startsWith('replace:'));
    // The evidence photo went to the incoming unit.
    expect(app.server.requests.any((r) => r.url.path == '/v1/uploads/up-1/attach/asset/$incomingUnit'), isTrue);
  });

  testWidgets('a different outgoing unit goes to review, and an unknown incoming unit is registered, never invented',
      (tester) async {
    final app = await start(tester);
    await app.go('/replace/$positionUid');
    await app.tap('outgoing-other');
    await app.tap('scan-incoming');
    await scanTyped(app, 'UNKNOWN-9');
    expect(find.byKey(const Key('replace-register')), findsOneWidget);
    expect(app.server.sent('POST', '/v1/assets'), isEmpty); // nothing made from a name
  });

  testWidgets('a proposal reports why it waits', (tester) async {
    final app = await start(tester);
    await app.go('/replace/$positionUid');
    await app.tap('outgoing-other');
    await app.tap('scan-outgoing');
    await scanTyped(app, 'IP-NEW-1'); // the unit found in place is not the recorded one
    await app.tap('scan-incoming');
    await scanTyped(app, 'IP-NEW-1');
    await app.tap('replace-check');
    expect(find.textContaining('This goes to review: the outgoing unit differs'), findsOneWidget);
    await app.tap('replace-submit');
    expect(find.text('Submitted for review'), findsOneWidget);
    expect(find.textContaining('An approver confirms it'), findsOneWidget);
  });

  testWidgets('review items come one at a time with only the decisions allowed here', (tester) async {
    final app = await start(tester);
    await app.go('/reviews');
    expect(find.byKey(const Key('review-count')), findsOneWidget);
    // The first item (a source conflict) is for the web.
    expect(find.textContaining('Decide this on the web'), findsOneWidget);
    await tester.drag(find.byType(PageView), const Offset(-400, 0)); // swipe
    await tester.pumpAndSettle();
    expect(find.text('Outgoing unit differs from the record'), findsOneWidget);
    await app.tap('review-next'); // or the button

    expect(find.text('Proposed replacement'), findsOneWidget);
    final item = find.byWidgetPredicate((w) => w.key is ValueKey<String> &&
        (w.key! as ValueKey<String>).value.startsWith('decide-') &&
        (w.key! as ValueKey<String>).value.endsWith('-confirm'));
    await tester.tap(item);
    await tester.pumpAndSettle();
    expect(app.server.requests.any((r) => r.url.path.endsWith('/confirm')), isTrue);
    expect(find.textContaining('Proposed replacement: confirm'), findsOneWidget);
  });
}
