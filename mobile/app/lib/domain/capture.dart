/// What the capture and ticket screens work with (flutter-app-design §4.2 `capture`, `tickets`).
library;

import 'dart:typed_data';

/// A photo taken or chosen on the device, before it is uploaded.
class PickedPhoto {
  const PickedPhoto({required this.bytes, required this.name, required this.mimeType});

  final Uint8List bytes;
  final String name;
  final String mimeType;
}

/// When something happened, with the precision the person knows (I-TKT-4, revision §8.2).
enum WhenPrecision { instant, day, month }

class WhenInput {
  const WhenInput(this.at, this.precision);

  final DateTime at;
  final WhenPrecision precision;

  /// The temporal value ARGUS stores: the nominal instant, in UTC, truncated to the precision.
  Map<String, Object?> toJson() {
    final l = at.toLocal();
    final nominal = switch (precision) {
      WhenPrecision.instant => at.toUtc(),
      WhenPrecision.day => DateTime.utc(l.year, l.month, l.day),
      WhenPrecision.month => DateTime.utc(l.year, l.month),
    };
    return {'kind': 'date', 'nominal': nominal.toIso8601String(), 'precision': precision.name};
  }
}

/// One value a model proposed: never applied until the person takes it (revision §23.11).
class Proposal {
  const Proposal({
    required this.field,
    required this.value,
    this.label,
    this.confidence,
    this.evidence,
    this.grounded = true,
    this.method = 'ai_extracted',
  });

  final String field; // title, description, schema_uid, attributes.serial ...
  final Object? value;
  final String? label;
  final double? confidence;
  final String? evidence;
  final bool grounded;
  final String method; // draft | ai_extracted | ai_classified

  String get display {
    if (label != null) return label!;
    final v = value;
    if (v is Map && v['nominal'] is String) {
      // A time: shown in local time, to the precision it was read with.
      final at = DateTime.tryParse(v['nominal'] as String)?.toLocal();
      if (at == null) return '$v';
      String two(int n) => n.toString().padLeft(2, '0');
      final day = '${at.year}-${two(at.month)}-${two(at.day)}';
      return switch (v['precision']) {
        'month' => '${at.year}-${two(at.month)}',
        'day' => day,
        _ => '$day ${two(at.hour)}:${two(at.minute)}',
      };
    }
    return '$v';
  }

  bool get weak => !grounded || (confidence != null && confidence! < 0.6);
}

class Dropped {
  const Dropped(this.field, this.reason);

  final String field;
  final String reason;
}

/// A check the server's deterministic guide made on a draft (revision §23.5).
class GuideCheck {
  const GuideCheck({required this.id, required this.level, required this.message, this.field, this.links = const []});

  final String id;
  final String level; // error | warning | info
  final String message;
  final String? field;
  final List<({String uid, String name, String path})> links;

  bool get blocking => level == 'error';
}

class AssistResult {
  const AssistResult({
    required this.runId,
    this.proposals = const {},
    this.dropped = const [],
    this.hypotheses = const [],
    this.redacted = 0,
    this.checks = const [],
  });

  final String runId;
  final Map<String, Proposal> proposals;
  final List<Dropped> dropped;
  final List<String> hypotheses; // causes stay hypotheses (§23.7)
  final int redacted;
  final List<GuideCheck> checks;
}

class TicketKind {
  const TicketKind(this.uid, this.name);

  final String uid;
  final String name;

  bool get isIncident => name.trim().toLowerCase() == 'operational incident';
}

class EquipmentType {
  const EquipmentType(this.uid, this.name);

  final String uid;
  final String name;
}

class Comment {
  const Comment({required this.uid, required this.author, required this.body, this.at});

  final String uid;
  final String author;
  final String body;
  final DateTime? at;
}

class AttachmentInfo {
  const AttachmentInfo({required this.uid, required this.filename, this.mimeType, this.size});

  final String uid;
  final String filename;
  final String? mimeType;
  final int? size;
}

class TransitionOption {
  const TransitionOption({required this.to, required this.name, required this.toName, this.category, this.requires = const []});

  final String to;
  final String name;
  final String toName;
  final String? category; // open | active | waiting | done
  final List<String> requires; // comment | resolution | assignee

  bool get closes => category == 'done';
}

class TransitionResult {
  const TransitionResult({required this.state, required this.proposed});

  final String state;
  final bool proposed; // 202: a closure from the field waits for a person online (A70)
}

class NotificationItem {
  const NotificationItem({required this.id, required this.title, this.issueUid, this.kind, this.read = false, this.at});

  final int id;
  final String title;
  final String? issueUid;
  final String? kind;
  final bool read;
  final DateTime? at;
}
