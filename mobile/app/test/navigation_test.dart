import 'package:argus_field/domain/capture.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('six destinations along the bottom, each keeping its place', (tester) async {
    final r = await start(tester);
    expect(find.byKey(const Key('nav-bar')), findsOneWidget);
    await r.type('home-search', 'ion');

    await r.tap('nav-tickets');
    expect(find.byKey(const Key('tickets-list')), findsOneWidget);
    await r.tap('nav-documents');
    expect(find.byKey(const Key('documents-list')), findsOneWidget);
    await r.tap('nav-assets');
    expect(find.byKey(const Key('assets-list')), findsOneWidget);
    await r.tap('nav-graph');
    expect(find.byKey(const Key('graph-search')), findsOneWidget);
    await r.tap('nav-ask');
    expect(find.text('Ask ARGUS'), findsOneWidget);

    await r.tap('nav-home');
    expect(find.widgetWithText(TextField, 'ion'), findsOneWidget, reason: 'home kept what was typed');
  });

  testWidgets('a record opened from a destination covers the bar, and going back returns to it', (tester) async {
    final r = await start(tester);
    await r.tap('nav-tickets');
    await r.tap('ticket-$ticketUid');
    expect(find.byKey(const Key('ticket-title')), findsOneWidget);
    expect(find.byKey(const Key('nav-bar')), findsNothing);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('tickets-list')), findsOneWidget);
  });

  testWidgets('the drawer holds the account, settings, about and help', (tester) async {
    final r = await start(tester);
    await r.tap('nav-menu');
    for (final k in ['drawer-workspace', 'drawer-inbox', 'drawer-signout', 'drawer-settings', 'drawer-help', 'drawer-about',
        'drawer-privacy']) {
      expect(find.byKey(Key(k)), findsOneWidget, reason: k);
    }
    await r.tap('drawer-settings');
    expect(find.byKey(const Key('settings-theme')), findsOneWidget);
    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();
    expect(Theme.of(tester.element(find.byKey(const Key('settings-theme')))).brightness, Brightness.dark);
  });

  testWidgets('equipment is browsed a page at a time: searched, sorted and narrowed to a type', (tester) async {
    final r = await start(tester);
    await r.tap('nav-assets');
    expect(find.text('Gauge arc 3'), findsOneWidget);
    expect(find.text('3'), findsWidgets);
    final first = r.server.requests.lastWhere((q) => q.url.path == '/v1/assets');
    expect(first.url.queryParameters, containsPair('limit', '50'));
    expect(first.url.queryParameters, containsPair('sort', 'name'));

    await tester.tap(find.byKey(const Key('sort-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sort-updated')));
    await tester.pumpAndSettle();
    final sorted = r.server.requests.lastWhere((q) => q.url.path == '/v1/assets').url.queryParameters;
    expect(sorted['sort'], 'updated');
    expect(sorted['order'], 'desc', reason: 'newest first');
    final names = tester.widgetList<ListTile>(find.byType(ListTile))
        .map((t) => (t.title as Text?)?.data)
        .whereType<String>()
        .toList();
    expect(names.take(3), ['Ion pump gun area 2', 'Gauge arc 3', 'Ion pump linac 1']);

    await r.tap('type-filter');
    expect(find.text('2'), findsWidgets, reason: 'each type shows how many it has');
    await r.tap('type-slice-20463f:argus-object:vacuum-gauge');
    final typed = r.server.requests.lastWhere((q) => q.url.path == '/v1/assets').url.queryParameters;
    expect(typed['schema_uid'], 'slice-20463f:argus-object:vacuum-gauge');
    expect(typed['include_subtypes'], 'true');
    expect(find.text('Gauge arc 3'), findsOneWidget);
    expect(find.text('Ion pump linac 1'), findsNothing);

    await r.type('assets-search', 'arc');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(r.server.requests.lastWhere((q) => q.url.path == '/v1/assets').url.queryParameters['q'], 'arc');
  });

  testWidgets('tickets sort by title, creation or change', (tester) async {
    final r = await start(tester);
    await r.tap('nav-tickets');
    await tester.tap(find.text('All'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sort-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sort-name')));
    await tester.pumpAndSettle();
    final titles = tester.widgetList<ListTile>(find.descendant(
            of: find.byKey(const Key('tickets-list')), matching: find.byType(ListTile)))
        .map((t) => (t.title as Text).data!)
        .toList();
    expect(titles, [...titles]..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase())));
  });

  test('a type includes every type below it, and is placed in the hierarchy', () {
    final tree = TypeTree([
      TypeNode(uid: 'asset', name: 'Asset'),
      TypeNode(uid: 'vacuum', name: 'Vacuum', parentUid: 'asset'),
      TypeNode(uid: 'pump', name: 'Ion Pump', parentUid: 'vacuum'),
      TypeNode(uid: 'gauge', name: 'Gauge', parentUid: 'vacuum'),
      TypeNode(uid: 'magnet', name: 'Magnet', parentUid: 'asset'),
    ]);
    expect(tree.roots.map((t) => t.uid), ['asset']);
    expect(tree.path('pump').map((t) => t.name), ['Asset', 'Vacuum', 'Ion Pump']);
    expect(tree.subtree('vacuum'), {'vacuum', 'pump', 'gauge'});
    expect(tree.subtree('magnet'), {'magnet'});
  });

  testWidgets('the privacy policy is reachable before signing in, and from the drawer', (tester) async {
    await start(tester, stored: const {});
    expect(find.byKey(const Key('signin-privacy')), findsOneWidget);
    expect(testConfig.privacyPolicy.toString(), 'https://argus.test/privacy.html');
  });
}
