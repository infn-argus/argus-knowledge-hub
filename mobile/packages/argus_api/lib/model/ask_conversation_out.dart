//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AskConversationOut {
  /// Returns a new [AskConversationOut] instance.
  AskConversationOut({
    this.createdAt,
    required this.id,
    required this.title,
    this.updatedAt,
  });

  DateTime? createdAt;

  String id;

  String title;

  DateTime? updatedAt;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AskConversationOut &&
    other.createdAt == createdAt &&
    other.id == id &&
    other.title == title &&
    other.updatedAt == updatedAt;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (createdAt == null ? 0 : createdAt!.hashCode) +
    (id.hashCode) +
    (title.hashCode) +
    (updatedAt == null ? 0 : updatedAt!.hashCode);

  @override
  String toString() => 'AskConversationOut[createdAt=$createdAt, id=$id, title=$title, updatedAt=$updatedAt]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.createdAt != null) {
      json[r'created_at'] = this.createdAt!.toUtc().toIso8601String();
    } else {
      json[r'created_at'] = null;
    }
      json[r'id'] = this.id;
      json[r'title'] = this.title;
    if (this.updatedAt != null) {
      json[r'updated_at'] = this.updatedAt!.toUtc().toIso8601String();
    } else {
      json[r'updated_at'] = null;
    }
    return json;
  }

  /// Returns a new [AskConversationOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AskConversationOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AskConversationOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AskConversationOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AskConversationOut(
        createdAt: mapDateTime(json, r'created_at', r''),
        id: mapValueOfType<String>(json, r'id')!,
        title: mapValueOfType<String>(json, r'title')!,
        updatedAt: mapDateTime(json, r'updated_at', r''),
      );
    }
    return null;
  }

  static List<AskConversationOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AskConversationOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AskConversationOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AskConversationOut> mapFromJson(dynamic json) {
    final map = <String, AskConversationOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AskConversationOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AskConversationOut-objects as value to a dart map
  static Map<String, List<AskConversationOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AskConversationOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AskConversationOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'id',
    'title',
  };
}

