import 'package:argus_field/features/scan/text_reader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_server.dart';
import 'harness.dart';

const _plate = '''
AGILENT TECHNOLOGIES
VacIon Plus 300 StarCell
Model 9191145
S/N: IT21094711
230 V 50 Hz 2021
''';

void main() {
  test('what in a nameplate could be a label, the value after S/N first', () {
    final c = labelCandidates(_plate);
    expect(c.first, 'IT21094711');
    expect(c, contains('9191145'));
    expect(c, isNot(contains('230')), reason: 'a voltage is not a label');
    expect(c, isNot(contains('AGILENT')), reason: 'nor a word');
    expect(labelCandidates('Inventario n. INV-0042 / ASSET TAG: 77-1234'), containsAll(['INV-0042', '77-1234']));
    expect(labelCandidates('Matricola: 00012345'), ['00012345']);
  });

  testWidgets('printed text is read, and the first value that finds a record opens it', (tester) async {
    final r = await start(tester);
    r.texts.text = _plate;
    r.server.labelLookups['IT21094711'] = {
      'kind': 'asset', 'uid': ionPumpUid, 'key': 'SLICE-20463F-IP-0001', 'name': 'Ion pump gun area 2', 'type': 'Ion Pump',
    };
    await r.go('/scan');
    await r.tap('scan-read-text');
    expect(r.server.lookedUp.first, 'IT21094711', reason: 'the serial is tried first');
    expect(find.byKey(const Key('asset-name')), findsOneWidget);
  });

  testWidgets('nothing found: the person chooses what to look up', (tester) async {
    final r = await start(tester);
    r.texts.text = _plate;
    r.server.labelLookups['NOTHING'] = {};
    await r.go('/scan');
    await r.tap('scan-read-text');
    expect(find.text('No record carries these. Look one up anyway?'), findsOneWidget);
    expect(find.byKey(const Key('scan-candidate-IT21094711')), findsOneWidget);
    expect(r.server.lookedUp, containsAll(['IT21094711', '9191145']));
  });
}
