import 'dart:convert';

/// The server's problem shape (flutter-app-design §3.4), decided by `code`, never by the English text.
enum ProblemCode {
  stale,
  forbidden,
  invalid,
  invariant,
  conflict,
  ambiguous,
  notFound,
  tooLarge,
  clientTooOld,
  revoked,
  unauthenticated,
  offline,
  unknown,
}

class Problem implements Exception {
  Problem(this.code, this.message, {this.status, this.minimum, this.candidates = const []});

  final ProblemCode code;
  final String message;
  final int? status;
  final String? minimum;

  /// For `ambiguous`: the records a label value matches, for the person to choose from.
  final List<Map<String, Object?>> candidates;

  static const _codes = {
    'stale': ProblemCode.stale,
    'forbidden': ProblemCode.forbidden,
    'invalid': ProblemCode.invalid,
    'invariant': ProblemCode.invariant,
    'conflict': ProblemCode.conflict,
    'ambiguous': ProblemCode.ambiguous,
    'not_found': ProblemCode.notFound,
    'too_large': ProblemCode.tooLarge,
    'client_too_old': ProblemCode.clientTooOld,
    'revoked': ProblemCode.revoked,
  };

  /// A problem from an HTTP status and body, whatever shape the body has.
  factory Problem.fromResponse(int status, String? body) {
    Object? detail;
    try {
      detail = (jsonDecode(body ?? '') as Map<String, dynamic>)['detail'];
    } catch (_) {
      detail = null;
    }
    String message = 'The request failed ($status).';
    String? code;
    String? minimum;
    var candidates = const <Map<String, Object?>>[];
    if (detail is String) {
      message = detail;
    } else if (detail is Map) {
      message = (detail['error'] ?? message).toString();
      code = detail['code']?.toString();
      minimum = detail['minimum']?.toString();
      final c = detail['candidates'];
      if (c is List) {
        candidates = [for (final m in c) if (m is Map) m.map((k, v) => MapEntry(k.toString(), v))];
      }
    }
    final byStatus = switch (status) {
      401 => ProblemCode.unauthenticated,
      403 => ProblemCode.forbidden,
      404 => ProblemCode.notFound,
      409 => ProblemCode.conflict,
      413 => ProblemCode.tooLarge,
      422 => ProblemCode.invalid,
      426 => ProblemCode.clientTooOld,
      _ => ProblemCode.unknown,
    };
    return Problem(_codes[code] ?? byStatus, message, status: status, minimum: minimum, candidates: candidates);
  }

  @override
  String toString() => message;
}
