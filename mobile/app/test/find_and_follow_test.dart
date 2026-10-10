import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('an advanced search runs a JQL query, says where it went wrong, and opens a hit', (tester) async {
    final app = await start(tester);
    await app.go('/query');
    await tester.tap(find.text('Equipment'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('query-jql')), 'status =');
    await app.tap('query-run');
    expect(find.textContaining('Expected a value'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('query-jql')), 'type = "Ion Pump" ORDER BY key');
    await app.tap('query-run');
    expect(find.text('1 found'.toUpperCase()), findsOneWidget);
    expect(find.text('Ion pump 7'), findsOneWidget);
    expect(app.server.requests.any((r) =>
        r.url.path == '/v1/search/jql' && r.url.queryParameters['entity'] == 'assets'), isTrue);
    await app.tap('query-hit-$ionPumpUid');
    expect(find.byKey(const Key('asset-name')), findsOneWidget);
  });

  testWidgets('keys can be hidden: records are then named by name and title only', (tester) async {
    final app = await start(tester);
    await app.go('/query');
    await tester.tap(find.text('Equipment'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('query-jql')), 'type = "Ion Pump"');
    await app.tap('query-run');
    expect(find.textContaining('S7C415E:AST:IP-07'), findsOneWidget);

    await app.go('/settings');
    await app.tap('settings-show-keys');
    await app.go('/query');
    await tester.tap(find.text('Equipment'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('query-jql')), 'type = "Ion Pump"');
    await app.tap('query-run');
    expect(find.text('Ion pump 7'), findsOneWidget);
    expect(find.textContaining('S7C415E:AST:IP-07'), findsNothing);
  });

  testWidgets('a piece of equipment can be followed from its page', (tester) async {
    final app = await start(tester);
    await app.go('/asset/$ionPumpUid');
    await app.tap('follow-asset');
    expect(app.server.following, contains('asset/$ionPumpUid'));
    expect(find.byIcon(Icons.notifications_active), findsOneWidget);
  });
}
