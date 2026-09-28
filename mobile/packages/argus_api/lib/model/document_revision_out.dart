//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentRevisionOut {
  /// Returns a new [DocumentRevisionOut] instance.
  DocumentRevisionOut({
    this.approvedAt,
    this.approvedBy,
    required this.attributes,
    this.authoredBy,
    this.bodyMarkdown,
    required this.createdAt,
    required this.documentUid,
    this.nextReviewDue,
    this.publishedAt,
    this.reviewComment,
    required this.revisionNumber,
    required this.state,
    required this.steps,
    this.submittedAt,
    this.supersededByUid,
    required this.uid,
    required this.updatedAt,
    this.validFrom,
    this.validUntil,
  });

  DateTime? approvedAt;

  String? approvedBy;

  Object attributes;

  String? authoredBy;

  String? bodyMarkdown;

  DateTime createdAt;

  String documentUid;

  DateTime? nextReviewDue;

  DateTime? publishedAt;

  String? reviewComment;

  int revisionNumber;

  String state;

  Object? steps;

  DateTime? submittedAt;

  String? supersededByUid;

  String uid;

  DateTime updatedAt;

  DateTime? validFrom;

  DateTime? validUntil;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentRevisionOut &&
    other.approvedAt == approvedAt &&
    other.approvedBy == approvedBy &&
    other.attributes == attributes &&
    other.authoredBy == authoredBy &&
    other.bodyMarkdown == bodyMarkdown &&
    other.createdAt == createdAt &&
    other.documentUid == documentUid &&
    other.nextReviewDue == nextReviewDue &&
    other.publishedAt == publishedAt &&
    other.reviewComment == reviewComment &&
    other.revisionNumber == revisionNumber &&
    other.state == state &&
    other.steps == steps &&
    other.submittedAt == submittedAt &&
    other.supersededByUid == supersededByUid &&
    other.uid == uid &&
    other.updatedAt == updatedAt &&
    other.validFrom == validFrom &&
    other.validUntil == validUntil;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (approvedAt == null ? 0 : approvedAt!.hashCode) +
    (approvedBy == null ? 0 : approvedBy!.hashCode) +
    (attributes.hashCode) +
    (authoredBy == null ? 0 : authoredBy!.hashCode) +
    (bodyMarkdown == null ? 0 : bodyMarkdown!.hashCode) +
    (createdAt.hashCode) +
    (documentUid.hashCode) +
    (nextReviewDue == null ? 0 : nextReviewDue!.hashCode) +
    (publishedAt == null ? 0 : publishedAt!.hashCode) +
    (reviewComment == null ? 0 : reviewComment!.hashCode) +
    (revisionNumber.hashCode) +
    (state.hashCode) +
    (steps == null ? 0 : steps!.hashCode) +
    (submittedAt == null ? 0 : submittedAt!.hashCode) +
    (supersededByUid == null ? 0 : supersededByUid!.hashCode) +
    (uid.hashCode) +
    (updatedAt.hashCode) +
    (validFrom == null ? 0 : validFrom!.hashCode) +
    (validUntil == null ? 0 : validUntil!.hashCode);

  @override
  String toString() => 'DocumentRevisionOut[approvedAt=$approvedAt, approvedBy=$approvedBy, attributes=$attributes, authoredBy=$authoredBy, bodyMarkdown=$bodyMarkdown, createdAt=$createdAt, documentUid=$documentUid, nextReviewDue=$nextReviewDue, publishedAt=$publishedAt, reviewComment=$reviewComment, revisionNumber=$revisionNumber, state=$state, steps=$steps, submittedAt=$submittedAt, supersededByUid=$supersededByUid, uid=$uid, updatedAt=$updatedAt, validFrom=$validFrom, validUntil=$validUntil]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.approvedAt != null) {
      json[r'approved_at'] = this.approvedAt!.toUtc().toIso8601String();
    } else {
      json[r'approved_at'] = null;
    }
    if (this.approvedBy != null) {
      json[r'approved_by'] = this.approvedBy;
    } else {
      json[r'approved_by'] = null;
    }
      json[r'attributes'] = this.attributes;
    if (this.authoredBy != null) {
      json[r'authored_by'] = this.authoredBy;
    } else {
      json[r'authored_by'] = null;
    }
    if (this.bodyMarkdown != null) {
      json[r'body_markdown'] = this.bodyMarkdown;
    } else {
      json[r'body_markdown'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
      json[r'document_uid'] = this.documentUid;
    if (this.nextReviewDue != null) {
      json[r'next_review_due'] = _dateFormatter.format(this.nextReviewDue!.toUtc());
    } else {
      json[r'next_review_due'] = null;
    }
    if (this.publishedAt != null) {
      json[r'published_at'] = this.publishedAt!.toUtc().toIso8601String();
    } else {
      json[r'published_at'] = null;
    }
    if (this.reviewComment != null) {
      json[r'review_comment'] = this.reviewComment;
    } else {
      json[r'review_comment'] = null;
    }
      json[r'revision_number'] = this.revisionNumber;
      json[r'state'] = this.state;
    if (this.steps != null) {
      json[r'steps'] = this.steps;
    } else {
      json[r'steps'] = null;
    }
    if (this.submittedAt != null) {
      json[r'submitted_at'] = this.submittedAt!.toUtc().toIso8601String();
    } else {
      json[r'submitted_at'] = null;
    }
    if (this.supersededByUid != null) {
      json[r'superseded_by_uid'] = this.supersededByUid;
    } else {
      json[r'superseded_by_uid'] = null;
    }
      json[r'uid'] = this.uid;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
    if (this.validFrom != null) {
      json[r'valid_from'] = _dateFormatter.format(this.validFrom!.toUtc());
    } else {
      json[r'valid_from'] = null;
    }
    if (this.validUntil != null) {
      json[r'valid_until'] = _dateFormatter.format(this.validUntil!.toUtc());
    } else {
      json[r'valid_until'] = null;
    }
    return json;
  }

  /// Returns a new [DocumentRevisionOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentRevisionOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentRevisionOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentRevisionOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentRevisionOut(
        approvedAt: mapDateTime(json, r'approved_at', r''),
        approvedBy: mapValueOfType<String>(json, r'approved_by'),
        attributes: mapValueOfType<Object>(json, r'attributes')!,
        authoredBy: mapValueOfType<String>(json, r'authored_by'),
        bodyMarkdown: mapValueOfType<String>(json, r'body_markdown'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        documentUid: mapValueOfType<String>(json, r'document_uid')!,
        nextReviewDue: mapDateTime(json, r'next_review_due', r''),
        publishedAt: mapDateTime(json, r'published_at', r''),
        reviewComment: mapValueOfType<String>(json, r'review_comment'),
        revisionNumber: mapValueOfType<int>(json, r'revision_number')!,
        state: mapValueOfType<String>(json, r'state')!,
        steps: mapValueOfType<Object>(json, r'steps'),
        submittedAt: mapDateTime(json, r'submitted_at', r''),
        supersededByUid: mapValueOfType<String>(json, r'superseded_by_uid'),
        uid: mapValueOfType<String>(json, r'uid')!,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        validFrom: mapDateTime(json, r'valid_from', r''),
        validUntil: mapDateTime(json, r'valid_until', r''),
      );
    }
    return null;
  }

  static List<DocumentRevisionOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentRevisionOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentRevisionOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentRevisionOut> mapFromJson(dynamic json) {
    final map = <String, DocumentRevisionOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentRevisionOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentRevisionOut-objects as value to a dart map
  static Map<String, List<DocumentRevisionOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentRevisionOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentRevisionOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'attributes',
    'created_at',
    'document_uid',
    'revision_number',
    'state',
    'steps',
    'uid',
    'updated_at',
  };
}

