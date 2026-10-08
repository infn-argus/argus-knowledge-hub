import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('the document list says which have nothing published yet, and opens one', (tester) async {
    final r = await start(tester);
    await r.tap('nav-documents');
    expect(find.text('Ion pump replacement'), findsOneWidget);
    expect(find.textContaining('DOC-0002 · not published yet'), findsOneWidget);
    await r.tap('document-$documentUid');
    expect(find.byKey(const Key('doc-title')), findsOneWidget);
  });

  testWidgets('a document written from a record is a draft that describes that record', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await tester.dragUntilVisible(find.byKey(const Key('asset-write-document')),
        find.byKey(const Key('asset-body-list')), const Offset(0, -300));
    await r.tap('asset-write-document');

    await r.type('doc-write-title', 'Ion pump HV trip');
    await r.type('doc-write-body', '# Check\n\nRead the controller log.');
    await tester.tap(find.text('Preview'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('doc-write-preview')), findsOneWidget);
    expect(find.text('Check'), findsOneWidget, reason: 'the Markdown heading is rendered, not shown as "# Check"');
    await r.tap('doc-write-save');

    final created = r.server.sent('POST', '/v1/documents').single;
    expect(created['title'], 'Ion pump HV trip');
    expect(created['body_markdown'], '# Check\n\nRead the controller log.');
    final uid = created['uid'] as String;
    final relation = r.server.sent('POST', '/v1/documents/$uid/relations').single;
    expect(relation, {'to_type': 'asset', 'to_uid': ionPumpUid, 'relation_type': 'describes'});
  });

  testWidgets('a draft is edited (only its text sent) and sent for review', (tester) async {
    final r = await start(tester);
    await r.go('/document/$draftUid');
    expect(find.text('No current revision. There is nothing to work from.'), findsOneWidget,
        reason: 'a draft is never presented as something to work from');
    expect(find.text('Revision 1 · Draft'), findsOneWidget);

    await r.tap('doc-edit-draft');
    expect(find.widgetWithText(TextField, '# Bake-out\n\nHeat to 150 °C.'), findsOneWidget);
    await r.type('doc-write-body', '# Bake-out\n\nHeat to 120 °C for 48 h.');
    await r.tap('doc-write-save');
    final put = r.server.requests.lastWhere((q) => q.method == 'PUT');
    expect(put.url.path, '/v1/documents/$draftUid/revisions/$draftUid-r1');
    expect(jsonDecode(put.body), {'body_markdown': '# Bake-out\n\nHeat to 120 °C for 48 h.'});

    await r.tap('doc-submit');
    expect(r.server.requests.where((q) => q.method == 'POST' && q.url.path.endsWith('/submit')), hasLength(1));
  });

  testWidgets('the next step follows the revision: an approved one is published, not edited', (tester) async {
    final r = await start(tester);
    r.server.draftRevisionState = 'approved';
    await r.go('/document/$draftUid');
    expect(find.text('Revision 1 · Approved'), findsOneWidget);
    expect(find.byKey(const Key('doc-edit-draft')), findsNothing);
    expect(find.byKey(const Key('doc-submit')), findsNothing);
    await r.tap('doc-publish');
    expect(r.server.requests.where((q) => q.method == 'POST' && q.url.path.endsWith('/publish')), hasLength(1));
  });

  testWidgets('a published document starts a new revision from its published text', (tester) async {
    final r = await start(tester);
    await r.go('/document/$documentUid');
    expect(find.byKey(const Key('doc-workflow')), findsNothing, reason: 'nothing is in progress');
    await r.tap('doc-new-revision');
    final sent = r.server.sent('POST', '/v1/documents/$documentUid/revisions').single;
    expect(sent, {'body_markdown': '# Ion pump replacement'});
  });

  testWidgets('an imported document, whose uid is not a UUID, opens as itself — not resolved as a code', (tester) async {
    const imported = 'olog-sparc-sparc-151';
    final r = await start(tester);
    http.Response json(Object body) => http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json'});
    final doc = fixtureJson('document') as Map<String, dynamic>;
    final current = fixtureJson('document_current') as Map<String, dynamic>;
    r.server.routes['GET /v1/documents/$imported'] = json({...doc, 'uid': imported, 'title': 'Olog entry 151'});
    r.server.routes['GET /v1/documents/$imported/current'] = json({...current, 'document_uid': imported});
    r.server.routes['GET /v1/documents/$imported/revisions'] = json([]);
    await r.go('/document/$imported');
    expect(find.text('Olog entry 151'), findsOneWidget);
    expect(r.server.requests.where((q) => q.url.path == '/v1/links/resolve'), isEmpty);
  });

  testWidgets('a document code in a link is still resolved', (tester) async {
    final r = await start(tester);
    await r.go('/document/DOC-0001');
    expect(r.server.requests.where((q) => q.url.path == '/v1/links/resolve'), isNotEmpty,
        reason: 'no record has the uid DOC-0001: it is looked up as a code');
  });
}
