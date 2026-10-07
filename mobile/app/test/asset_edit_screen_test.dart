import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

void main() {
  testWidgets('editing respects the type: a number field only takes a number, a photo can fill a text field, '
      'and saving sends the version read as If-Match', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await r.tap('asset-edit'); // a real push, so Save's pop back to the record has somewhere to go

    expect(find.text('Pumping speed (l/s)'), findsOneWidget);
    expect(find.widgetWithText(TextField, '120.5'), findsOneWidget, reason: 'the stored value is shown, pre-filled');

    // An enumeration is stored and matched by its label ("In service"), not its id ("in_service") — the
    // two commonly differ. The dropdown must show the record's actual value without crashing, and change
    // to another option's label when picked.
    expect(find.text('In service'), findsOneWidget);
    await tester.tap(find.byKey(const Key('attr-status')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Planned').last);
    await tester.pumpAndSettle();

    // Typing letters into a number field and trying to save is refused, with a reason — not silently coerced.
    await r.type('attr-pumping_speed-0', 'not a number');
    await r.tap('asset-edit-save');
    expect(find.textContaining('Not a number'), findsOneWidget);
    await r.type('attr-pumping_speed-0', '131.2');

    // A photo of the nameplate proposes a value for one field; nothing is written until it is taken.
    await r.tap('attr-manufacturer-0-scan');
    expect(r.photos.taken, 1);
    expect(find.text('manufacturer: Agilent'), findsOneWidget, reason: 'proposed, not yet written to the field');
    await r.tap('take-attributes.manufacturer');
    expect(find.widgetWithText(TextField, 'Agilent'), findsOneWidget);

    await r.tap('asset-edit-save');

    final put = r.server.requests.lastWhere((q) => q.method == 'PUT' && q.url.path == '/v1/assets/$ionPumpUid');
    expect(put.headers['If-Match'], '"5"', reason: 'the version read with the record, so a stale edit is refused');
    final sent = jsonDecode(put.body)['attributes'] as Map;
    expect(sent['pumping_speed'], 131.2);
    expect(sent['manufacturer'], 'Agilent');
    expect(sent['nominal_voltage'], 24); // untouched fields travel unchanged
    expect(sent['status'], 'Planned', reason: 'the label is sent, matching what the web form writes');
    expect(find.byKey(const Key('asset-edit-save')), findsNothing, reason: 'saving returns to the record, not stays on the form');
  });

  testWidgets('a reference attribute offers a search among records of its target type, not a raw uid '
      'text field', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await r.tap('asset-edit');
    await tester.drag(find.byKey(const Key('asset-edit-list')), const Offset(0, -2000));
    await tester.pumpAndSettle();

    // The record's current reference is shown by name, not as a bare uid.
    expect(find.text('PM-ACE2 · Ace 2 a2A1920-51gmBAS'), findsOneWidget);

    // Focusing it shows every candidate right away, not just the ones matching its own already-picked
    // display text (which nothing else would match) — the field must not look unusable until cleared.
    await tester.tap(find.byKey(const Key('attr-product_model-0')));
    await tester.pumpAndSettle();
    expect(find.text('PM-TURBO350 · TURBO350'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('attr-product_model-0')), 'turbo');
    await tester.pumpAndSettle();
    await tester.tap(find.text('PM-TURBO350 · TURBO350').last);
    await tester.pumpAndSettle();

    await tester.drag(find.byKey(const Key('asset-edit-list')), const Offset(0, -500));
    await tester.pumpAndSettle();
    await r.tap('asset-edit-save');

    final put = r.server.requests.lastWhere((q) => q.method == 'PUT' && q.url.path == '/v1/assets/$ionPumpUid');
    final sent = jsonDecode(put.body)['attributes'] as Map;
    expect(sent['product_model'], 'pm-turbo350');
  });

  testWidgets('a field kind the field app cannot yet edit (its type needs the web\'s picker) is named, not '
      'offered as a text box that could never hold a valid value', (tester) async {
    final r = await start(tester);
    await r.go('/asset/$ionPumpUid');
    await r.tap('asset-edit');
    await tester.drag(find.byKey(const Key('asset-edit-list')), const Offset(0, -2000));
    await tester.pumpAndSettle();
    expect(find.text('EDITED ON THE WEB'), findsOneWidget);
    expect(find.text('Responsible'), findsOneWidget);
    expect(find.byKey(const Key('attr-responsible-0')), findsNothing);
  });
}
