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

// --------------------------------------------------------------------------- replacement and review (M3)

class BriefRecord {
  const BriefRecord({this.uid, this.key, this.name, this.type, this.restricted = false});

  final String? uid;
  final String? key;
  final String? name;
  final String? type;
  final bool restricted;

  String get label => restricted ? 'Restricted record' : [key, name].whereType<String>().join(' · ');

  static BriefRecord? fromJson(Object? o) => o is Map
      ? BriefRecord(
          uid: o['uid']?.toString(),
          key: o['key']?.toString(),
          name: o['name']?.toString(),
          type: o['type']?.toString(),
          restricted: o['restricted'] == true)
      : null;
}

class SegmentConsequence {
  const SegmentConsequence({required this.name, required this.status, required this.safetyClass, this.reason});

  final String name;
  final String status; // attaches | confirmation_required | unresolved | not_applicable
  final String safetyClass;
  final String? reason;

  bool get needsConfirmation => status == 'confirmation_required' || status == 'unresolved';
}

/// What the server says a replacement would do (flutter-app-design §8 steps 6 and 8).
class ReplacementPreview {
  const ReplacementPreview({
    required this.outcome,
    this.reasons = const [],
    this.checks = const [],
    this.currentInstallationUid,
    this.currentUnit,
    this.incoming,
    this.accessPoints = const [],
    this.segments = const [],
    this.hiddenSegments = 0,
    this.documents = const [],
    this.openTickets = const [],
  });

  final String outcome; // apply | propose | refused
  final List<String> reasons;
  final List<GuideCheck> checks;
  final String? currentInstallationUid;
  final BriefRecord? currentUnit;
  final BriefRecord? incoming;
  final List<BriefRecord> accessPoints;
  final List<SegmentConsequence> segments;
  final int hiddenSegments;
  final List<({String uid, String title})> documents;
  final List<({String uid, String title})> openTickets;

  bool get refused => outcome == 'refused';
}

class ReplacementResult {
  const ReplacementResult({required this.applied, this.reasons = const [], this.reviewItem, this.discrepancyItem});

  final bool applied;
  final List<String> reasons;
  final String? reviewItem;
  final String? discrepancyItem;
}

/// One review item routed to the person, with the decisions the field client may take.
class ReviewItem {
  const ReviewItem({
    required this.key,
    required this.kind,
    required this.queue,
    this.age = 0,
    this.overdue = false,
    this.record,
    this.detail = const {},
    this.decisions = const [],
  });

  final String key; // conflict:<id> | proposal:<claim>:<uid>:<predicate> | revision:<id>
  final String kind;
  final String queue;
  final int age;
  final bool overdue;
  final BriefRecord? record;
  final Map<String, Object?> detail;
  final List<String> decisions;

  String get id => key.split(':')[1];

  String get title => switch (kind) {
        'replacement_proposal' => 'Proposed replacement',
        'outgoing_discrepancy' => 'Outgoing unit differs from the record',
        'stale_command' => 'A change made against an older version',
        'ai_proposal' => 'Value proposed by the assistant',
        'port_confirmation_required' => 'Port to confirm',
        'identity_candidate' => 'Possible duplicate',
        _ => kind.replaceAll('_', ' '),
      };
}

/// A workspace's types of one kind (equipment, tickets, documents) as the hierarchy they form — the web's
/// type tree. A type includes the records of every type below it.
class TypeTree {
  TypeTree(List<TypeNode> all) : byUid = {for (final t in all) t.uid: t} {
    for (final t in all) {
      final parent = t.parentUid == null ? null : byUid[t.parentUid];
      if (parent != null) {
        parent.children.add(t);
      } else {
        roots.add(t);
      }
    }
    void sort(List<TypeNode> ns) {
      ns.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      for (final n in ns) {
        sort(n.children);
      }
    }

    sort(roots);
  }

  final Map<String, TypeNode> byUid;
  final List<TypeNode> roots = [];

  /// From the top of the hierarchy down to [uid].
  List<TypeNode> path(String? uid) {
    final out = <TypeNode>[];
    var t = uid == null ? null : byUid[uid];
    while (t != null && !out.contains(t)) {
      out.insert(0, t);
      t = t.parentUid == null ? null : byUid[t.parentUid];
    }
    return out;
  }

  /// [uid] and every type below it.
  Set<String> subtree(String uid) {
    final out = <String>{};
    void walk(TypeNode t) {
      if (out.add(t.uid)) t.children.forEach(walk);
    }

    final t = byUid[uid];
    if (t != null) walk(t);
    return out;
  }
}

class TypeNode {
  TypeNode({required this.uid, required this.name, this.parentUid, this.concrete = true});

  final String uid;
  final String name;
  final String? parentUid;
  final bool concrete;
  final List<TypeNode> children = [];
}

/// A label on a record: a QR code, a serial, a barcode… — what a scan finds it by.
class AssetLabelInfo {
  const AssetLabelInfo({required this.uid, required this.type, required this.value, this.verified = false});

  final String uid;
  final String type;
  final String value;
  final bool verified;

  /// The kinds the app offers, a QR code first: the order a scan looks for them in.
  static const kinds = {
    'qrcode': 'QR code',
    'serial': 'Serial number',
    'barcode': 'Barcode',
    'datamatrix': 'DataMatrix',
    'inventory_number': 'Inventory number',
    'asset_tag': 'Asset tag',
    'rfid': 'RFID / NFC',
    'alias': 'Other name',
  };

  String get kindLabel => kinds[type] ?? type.replaceAll('_', ' ');
}
