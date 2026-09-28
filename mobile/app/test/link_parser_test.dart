import 'package:argus_field/core/link_parser.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const host = 'argus.infn.it';
  ScanResult parse(String s) => parseScan(s, linkHost: host);

  test('an https link on the ARGUS host is followed as its path', () {
    final r = parse('https://argus.infn.it/position/b3bc26da-32af-4d88-9551-612592db3359');
    expect(r, isA<ArgusPath>());
    expect((r as ArgusPath).path, '/position/b3bc26da-32af-4d88-9551-612592db3359');
    expect((parse('https://ARGUS.infn.it/ticket/SPARC-123?x=1') as ArgusPath).path, '/ticket/SPARC-123');
  });

  test('links elsewhere, other schemes and scripts are refused', () {
    for (final s in [
      'https://evil.example/asset/1',
      'https://argus.infn.it.evil.example/asset/1',
      'https://argus@evil.example/asset/1',
      'http://argus.infn.it/asset/1',
      'javascript:alert(1)',
      'JavaScript:alert(1)',
      'data:text/html,<script>1</script>',
      'tel:+390000000',
      'intent://scan/#Intent;scheme=zxing;end',
      'file:///etc/passwd',
    ]) {
      expect(parse(s), isA<Refused>(), reason: s);
    }
  });

  test('a record-less path on the ARGUS host is refused', () {
    expect(parse('https://argus.infn.it/admin'), isA<Refused>());
    expect(parse('https://argus.infn.it/'), isA<Refused>());
  });

  test('plain text is a label value to look up', () {
    expect((parse('  SPARC-1234 ') as LabelValue).value, 'SPARC-1234');
    expect((parse('S7C415E:POS:GUNSIP01') as LabelValue).value, 'S7C415E:POS:GUNSIP01');
    expect((parse('INV 0042') as LabelValue).value, 'INV 0042');
  });

  test('a bare ARGUS path is followed, other paths are labels', () {
    expect((parse('/asset/abc') as ArgusPath).path, '/asset/abc');
    expect(parse('/etc/passwd'), isA<LabelValue>());
  });

  test('empty, oversized and control-character labels are refused', () {
    expect(parse('   '), isA<Refused>());
    expect(parse('A' * 600), isA<Refused>());
    expect(parse('ABC\u0000DEF'), isA<Refused>());
  });
}
