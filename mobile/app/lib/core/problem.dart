import 'dart:convert';

/// The server's problem shape (flutter-app-design §3.4), decided by `code`, never by the English text.
enum ProblemCode {
  stale,
  forbidden,
  invalid,
  invariant,
  conflict,
  ambiguous,
  idempotencyMismatch,
  inProgress,
  expired,
  notFound,
  tooLarge,
  clientTooOld,
  revoked,
  unauthenticated,
  offline,
  unknown,
}

class Problem implements Exception {
  Problem(this.code, this.message,
      {this.status, this.minimum, this.candidates = const [], this.field, this.current, this.reviewItem, this.position});

  final ProblemCode code;
  final String message;
  final int? status;
  final String? minimum;

  /// For `ambiguous`: the records a label value matches, for the person to choose from.
  final List<Map<String, Object?>> candidates;

  /// The field the problem is about (`attributes.serial`, `If-Match`), when there is one.
  final String? field;

  /// For `stale` and some conflicts: the current state (version, values, offset).
  final Map<String, Object?>? current;

  /// When the server turned the command into a review item instead of applying it.
  final String? reviewItem;

  /// For a query that cannot be read: where in it (0-based).
  final int? position;

  static const _codes = {
    'stale': ProblemCode.stale,
    'forbidden': ProblemCode.forbidden,
    'invalid': ProblemCode.invalid,
    'invariant': ProblemCode.invariant,
    'conflict': ProblemCode.conflict,
    'ambiguous': ProblemCode.ambiguous,
    'idempotency_mismatch': ProblemCode.idempotencyMismatch,
    'in_progress': ProblemCode.inProgress,
    'expired': ProblemCode.expired,
    'unauthenticated': ProblemCode.unauthenticated,
    'not_found': ProblemCode.notFound,
    'too_large': ProblemCode.tooLarge,
    'client_too_old': ProblemCode.clientTooOld,
    'revoked': ProblemCode.revoked,
  };

  /// A problem from an HTTP status and body, whatever shape the body has.
  factory Problem.fromResponse(int status, String? body) {
    Object? detail;
    try {
      final decoded = jsonDecode(body ?? '') as Map<String, dynamic>;
      // The problem shape (revision §24.3 item 4); older servers send only `detail`.
      detail = decoded['problem'] is Map ? decoded['problem'] : decoded['detail'];
    } catch (_) {
      detail = null;
    }
    String message = 'The request failed ($status).';
    String? code;
    String? minimum;
    var candidates = const <Map<String, Object?>>[];
    String? field;
    Map<String, Object?>? current;
    String? reviewItem;
    int? position;
    if (detail is String) {
      message = detail;
    } else if (detail is Map) {
      message = (detail['error'] ?? message).toString();
      code = detail['code']?.toString();
      minimum = detail['minimum']?.toString();
      field = detail['field']?.toString();
      reviewItem = detail['review_item']?.toString();
      final pos = detail['position'];
      if (pos is num) position = pos.toInt();
      final cur = detail['current'];
      if (cur is Map) current = cur.map((k, v) => MapEntry(k.toString(), v));
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
    return Problem(_codes[code] ?? byStatus, message,
        status: status,
        minimum: minimum,
        candidates: candidates,
        field: field,
        current: current,
        reviewItem: reviewItem,
        position: position);
  }

  @override
  String toString() => message;
}
