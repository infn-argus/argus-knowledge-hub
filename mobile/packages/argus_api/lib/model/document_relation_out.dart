//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentRelationOut {
  /// Returns a new [DocumentRelationOut] instance.
  DocumentRelationOut({
    required this.createdAt,
    required this.fromDocumentUid,
    required this.id,
    required this.relationType,
    required this.toType,
    required this.toUid,
  });

  DateTime createdAt;

  String fromDocumentUid;

  int id;

  String relationType;

  String toType;

  String toUid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentRelationOut &&
    other.createdAt == createdAt &&
    other.fromDocumentUid == fromDocumentUid &&
    other.id == id &&
    other.relationType == relationType &&
    other.toType == toType &&
    other.toUid == toUid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (createdAt.hashCode) +
    (fromDocumentUid.hashCode) +
    (id.hashCode) +
    (relationType.hashCode) +
    (toType.hashCode) +
    (toUid.hashCode);

  @override
  String toString() => 'DocumentRelationOut[createdAt=$createdAt, fromDocumentUid=$fromDocumentUid, id=$id, relationType=$relationType, toType=$toType, toUid=$toUid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
      json[r'from_document_uid'] = this.fromDocumentUid;
      json[r'id'] = this.id;
      json[r'relation_type'] = this.relationType;
      json[r'to_type'] = this.toType;
      json[r'to_uid'] = this.toUid;
    return json;
  }

  /// Returns a new [DocumentRelationOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentRelationOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentRelationOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentRelationOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentRelationOut(
        createdAt: mapDateTime(json, r'created_at', r'')!,
        fromDocumentUid: mapValueOfType<String>(json, r'from_document_uid')!,
        id: mapValueOfType<int>(json, r'id')!,
        relationType: mapValueOfType<String>(json, r'relation_type')!,
        toType: mapValueOfType<String>(json, r'to_type')!,
        toUid: mapValueOfType<String>(json, r'to_uid')!,
      );
    }
    return null;
  }

  static List<DocumentRelationOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentRelationOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentRelationOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentRelationOut> mapFromJson(dynamic json) {
    final map = <String, DocumentRelationOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentRelationOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentRelationOut-objects as value to a dart map
  static Map<String, List<DocumentRelationOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentRelationOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentRelationOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'created_at',
    'from_document_uid',
    'id',
    'relation_type',
    'to_type',
    'to_uid',
  };
}

