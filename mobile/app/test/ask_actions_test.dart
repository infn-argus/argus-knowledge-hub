import 'dart:convert';

import 'package:argus_field/features/ask/ask_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'harness.dart';

http.Response _json(Object body) =>
    http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json'});

Future<Running> _ask(WidgetTester tester) async {
  final r = await start(tester);
  r.server.routes['GET /v1/ai/status'] = _json({'configured': true, 'enabled': true, 'validated': true, 'model': 'm'});
  await r.tap('nav-ask');
  return r;
}

void main() {
  test('a title from the first words', () {
    expect(firstLineOf('Venting sector 3. Close the gate valve first.'), 'Venting sector 3');
    expect(firstLineOf('# Bake-out\nHeat it'), 'Bake-out');
    expect(firstLineOf('x' * 100).length, 78);
  });

  testWidgets('a document is dictated: transcribed, edited, saved, with the recording kept on the draft',
      (tester) async {
    final r = await _ask(tester);
    r.server.routes['POST /v1/ai/transcribe'] =
        _json({'text': 'Venting sector 3. Close the gate valve, then open the vent slowly.'});
    await r.tap('ask-actions');
    await r.tap('ask-action-doc-voice');
    await r.tap('record-stop');

    expect(r.server.requests.where((q) => q.url.path == '/v1/ai/transcribe'), hasLength(1));
    expect(find.byKey(const Key('doc-write-seed')), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Venting sector 3'), findsOneWidget, reason: 'its title, from the first words');
    await r.tap('doc-write-save');

    final created = r.server.sent('POST', '/v1/documents').single;
    expect(created['body_markdown'], 'Venting sector 3. Close the gate valve, then open the vent slowly.');
    final upload = r.server.sent('POST', '/v1/uploads').single;
    expect(upload['content_type'], 'audio/mp4');
    final attach = r.server.requests.lastWhere((q) => q.url.path.contains('/attach/'));
    expect(attach.url.path, endsWith('/attach/document/${created['uid']}/revision/${created['uid']}-r1'));
  });

  testWidgets('a document is written from a photo of a page, and tidied by the assistant — with an undo',
      (tester) async {
    final r = await _ask(tester);
    r.texts.text = 'BAKE-OUT\nheat to 150 C for 48 h\nvent with dry nitrogen';
    r.server.routes['POST /v1/ai/draft-document'] =
        _json({'body_markdown': '# Bake-out\n\n1. Heat to 150 °C for 48 h.\n2. Vent with dry nitrogen.'});
    await r.tap('ask-actions');
    await r.tap('ask-action-doc-photo');
    expect(r.photos.taken, 1);
    expect(find.textContaining('vent with dry nitrogen'), findsOneWidget);

    await r.tap('doc-write-tidy');
    final asked = r.server.sent('POST', '/v1/ai/draft-document').single;
    expect(asked['notes'], contains('vent with dry nitrogen'));
    expect(find.textContaining('1. Heat to 150 °C'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();
    expect(find.textContaining('heat to 150 C'), findsOneWidget, reason: "the person's own text is back");
  });

  testWidgets('equipment is registered from a photo: the camera opens at once', (tester) async {
    final r = await _ask(tester);
    await r.tap('ask-actions');
    await r.tap('ask-action-register-photo');
    expect(find.text('Register equipment'), findsOneWidget);
    expect(r.photos.taken, 1);
  });
}
