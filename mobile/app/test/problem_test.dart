import 'package:argus_field/core/problem.dart';
import 'package:argus_field/domain/capture.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('the code decides, not the status or the text', () {
    final p = Problem.fromResponse(401, '{"detail":{"error":"This device was signed out.","code":"revoked"}}');
    expect(p.code, ProblemCode.revoked);
    expect(p.message, 'This device was signed out.');
  });

  test('a client too old carries the minimum version', () {
    final p = Problem.fromResponse(426, '{"detail":{"error":"Update","code":"client_too_old","minimum":"1.4.0"}}');
    expect(p.code, ProblemCode.clientTooOld);
    expect(p.minimum, '1.4.0');
  });

  test('without a code the status decides; any body is tolerated', () {
    expect(Problem.fromResponse(404, '{"detail":"Asset not found"}').code, ProblemCode.notFound);
    expect(Problem.fromResponse(404, '{"detail":"Asset not found"}').message, 'Asset not found');
    expect(Problem.fromResponse(401, 'not json').code, ProblemCode.unauthenticated);
    expect(Problem.fromResponse(500, null).code, ProblemCode.unknown);
  });

  test('a proposed time is shown in local time, to its precision', () {
    const month = Proposal(field: 'attributes.occurred_from', value: {'kind': 'date', 'nominal': '2026-09-01T00:00:00Z', 'precision': 'month'});
    expect(month.display, startsWith('2026-'));
    expect(month.display.length, 7);
    const labelled = Proposal(field: 'attributes.argus_impact', value: 'beam_down', label: 'Beam down');
    expect(labelled.display, 'Beam down');
  });

  test('the problem shape is read first, with its field, current state and review item', () {
    final p = Problem.fromResponse(409,
        '{"detail":{"error":"x"},"problem":{"error":"Changed since you read it.","code":"stale",'
        '"field":"attr:serial","current":{"version":42},"review_item":"c1"}}');
    expect(p.code, ProblemCode.stale);
    expect(p.message, 'Changed since you read it.');
    expect(p.field, 'attr:serial');
    expect(p.current, {'version': 42});
    expect(p.reviewItem, 'c1');
    expect(Problem.fromResponse(422, '{"detail":[],"problem":{"error":"reused","code":"idempotency_mismatch"}}').code,
        ProblemCode.idempotencyMismatch);
  });
}
