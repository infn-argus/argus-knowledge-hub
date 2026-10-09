//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DraftDocumentOut {
  /// Returns a new [DraftDocumentOut] instance.
  DraftDocumentOut({
    required this.bodyMarkdown,
    this.mentionedObjects = const [],
  });

  String bodyMarkdown;

  List<MentionedObject> mentionedObjects;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DraftDocumentOut &&
    other.bodyMarkdown == bodyMarkdown &&
    _deepEquality.equals(other.mentionedObjects, mentionedObjects);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (bodyMarkdown.hashCode) +
    (mentionedObjects.hashCode);

  @override
  String toString() => 'DraftDocumentOut[bodyMarkdown=$bodyMarkdown, mentionedObjects=$mentionedObjects]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'body_markdown'] = this.bodyMarkdown;
      json[r'mentioned_objects'] = this.mentionedObjects;
    return json;
  }

  /// Returns a new [DraftDocumentOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DraftDocumentOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DraftDocumentOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DraftDocumentOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DraftDocumentOut(
        bodyMarkdown: mapValueOfType<String>(json, r'body_markdown')!,
        mentionedObjects: MentionedObject.listFromJson(json[r'mentioned_objects']),
      );
    }
    return null;
  }

  static List<DraftDocumentOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DraftDocumentOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DraftDocumentOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DraftDocumentOut> mapFromJson(dynamic json) {
    final map = <String, DraftDocumentOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DraftDocumentOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DraftDocumentOut-objects as value to a dart map
  static Map<String, List<DraftDocumentOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DraftDocumentOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DraftDocumentOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'body_markdown',
  };
}

