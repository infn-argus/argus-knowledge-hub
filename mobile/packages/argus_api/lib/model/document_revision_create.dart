//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentRevisionCreate {
  /// Returns a new [DocumentRevisionCreate] instance.
  DocumentRevisionCreate({
    this.attributes,
    this.bodyMarkdown,
    this.nextReviewDue,
    this.steps,
    this.validFrom,
    this.validUntil,
  });

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? attributes;

  String? bodyMarkdown;

  DateTime? nextReviewDue;

  Object? steps;

  DateTime? validFrom;

  DateTime? validUntil;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentRevisionCreate &&
    other.attributes == attributes &&
    other.bodyMarkdown == bodyMarkdown &&
    other.nextReviewDue == nextReviewDue &&
    other.steps == steps &&
    other.validFrom == validFrom &&
    other.validUntil == validUntil;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (attributes == null ? 0 : attributes!.hashCode) +
    (bodyMarkdown == null ? 0 : bodyMarkdown!.hashCode) +
    (nextReviewDue == null ? 0 : nextReviewDue!.hashCode) +
    (steps == null ? 0 : steps!.hashCode) +
    (validFrom == null ? 0 : validFrom!.hashCode) +
    (validUntil == null ? 0 : validUntil!.hashCode);

  @override
  String toString() => 'DocumentRevisionCreate[attributes=$attributes, bodyMarkdown=$bodyMarkdown, nextReviewDue=$nextReviewDue, steps=$steps, validFrom=$validFrom, validUntil=$validUntil]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.attributes != null) {
      json[r'attributes'] = this.attributes;
    } else {
      json[r'attributes'] = null;
    }
    if (this.bodyMarkdown != null) {
      json[r'body_markdown'] = this.bodyMarkdown;
    } else {
      json[r'body_markdown'] = null;
    }
    if (this.nextReviewDue != null) {
      json[r'next_review_due'] = _dateFormatter.format(this.nextReviewDue!.toUtc());
    } else {
      json[r'next_review_due'] = null;
    }
    if (this.steps != null) {
      json[r'steps'] = this.steps;
    } else {
      json[r'steps'] = null;
    }
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

  /// Returns a new [DocumentRevisionCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentRevisionCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentRevisionCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentRevisionCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentRevisionCreate(
        attributes: mapValueOfType<Object>(json, r'attributes'),
        bodyMarkdown: mapValueOfType<String>(json, r'body_markdown'),
        nextReviewDue: mapDateTime(json, r'next_review_due', r''),
        steps: mapValueOfType<Object>(json, r'steps'),
        validFrom: mapDateTime(json, r'valid_from', r''),
        validUntil: mapDateTime(json, r'valid_until', r''),
      );
    }
    return null;
  }

  static List<DocumentRevisionCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentRevisionCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentRevisionCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentRevisionCreate> mapFromJson(dynamic json) {
    final map = <String, DocumentRevisionCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentRevisionCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentRevisionCreate-objects as value to a dart map
  static Map<String, List<DocumentRevisionCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentRevisionCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentRevisionCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}

