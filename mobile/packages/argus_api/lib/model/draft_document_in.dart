//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DraftDocumentIn {
  /// Returns a new [DraftDocumentIn] instance.
  DraftDocumentIn({
    this.documentTypeUid,
    this.notes,
    required this.title,
  });

  String? documentTypeUid;

  String? notes;

  String title;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DraftDocumentIn &&
    other.documentTypeUid == documentTypeUid &&
    other.notes == notes &&
    other.title == title;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (documentTypeUid == null ? 0 : documentTypeUid!.hashCode) +
    (notes == null ? 0 : notes!.hashCode) +
    (title.hashCode);

  @override
  String toString() => 'DraftDocumentIn[documentTypeUid=$documentTypeUid, notes=$notes, title=$title]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.documentTypeUid != null) {
      json[r'document_type_uid'] = this.documentTypeUid;
    } else {
      json[r'document_type_uid'] = null;
    }
    if (this.notes != null) {
      json[r'notes'] = this.notes;
    } else {
      json[r'notes'] = null;
    }
      json[r'title'] = this.title;
    return json;
  }

  /// Returns a new [DraftDocumentIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DraftDocumentIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DraftDocumentIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DraftDocumentIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DraftDocumentIn(
        documentTypeUid: mapValueOfType<String>(json, r'document_type_uid'),
        notes: mapValueOfType<String>(json, r'notes'),
        title: mapValueOfType<String>(json, r'title')!,
      );
    }
    return null;
  }

  static List<DraftDocumentIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DraftDocumentIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DraftDocumentIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DraftDocumentIn> mapFromJson(dynamic json) {
    final map = <String, DraftDocumentIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DraftDocumentIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DraftDocumentIn-objects as value to a dart map
  static Map<String, List<DraftDocumentIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DraftDocumentIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DraftDocumentIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'title',
  };
}

