import 'package:argus_field/core/problem.dart';
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
}
