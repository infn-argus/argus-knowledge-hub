//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AskConversationDetail {
  /// Returns a new [AskConversationDetail] instance.
  AskConversationDetail({
    this.createdAt,
    required this.id,
    this.messages = const [],
    required this.title,
    this.updatedAt,
  });

  DateTime? createdAt;

  String id;

  List<AskMessageOut> messages;

  String title;

  DateTime? updatedAt;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AskConversationDetail &&
    other.createdAt == createdAt &&
    other.id == id &&
    _deepEquality.equals(other.messages, messages) &&
    other.title == title &&
    other.updatedAt == updatedAt;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (createdAt == null ? 0 : createdAt!.hashCode) +
    (id.hashCode) +
    (messages.hashCode) +
    (title.hashCode) +
    (updatedAt == null ? 0 : updatedAt!.hashCode);

  @override
  String toString() => 'AskConversationDetail[createdAt=$createdAt, id=$id, messages=$messages, title=$title, updatedAt=$updatedAt]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.createdAt != null) {
      json[r'created_at'] = this.createdAt!.toUtc().toIso8601String();
    } else {
      json[r'created_at'] = null;
    }
      json[r'id'] = this.id;
      json[r'messages'] = this.messages;
      json[r'title'] = this.title;
    if (this.updatedAt != null) {
      json[r'updated_at'] = this.updatedAt!.toUtc().toIso8601String();
    } else {
      json[r'updated_at'] = null;
    }
    return json;
  }

  /// Returns a new [AskConversationDetail] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AskConversationDetail? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AskConversationDetail[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AskConversationDetail[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AskConversationDetail(
        createdAt: mapDateTime(json, r'created_at', r''),
        id: mapValueOfType<String>(json, r'id')!,
        messages: AskMessageOut.listFromJson(json[r'messages']),
        title: mapValueOfType<String>(json, r'title')!,
        updatedAt: mapDateTime(json, r'updated_at', r''),
      );
    }
    return null;
  }

  static List<AskConversationDetail> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AskConversationDetail>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AskConversationDetail.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AskConversationDetail> mapFromJson(dynamic json) {
    final map = <String, AskConversationDetail>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AskConversationDetail.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AskConversationDetail-objects as value to a dart map
  static Map<String, List<AskConversationDetail>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AskConversationDetail>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AskConversationDetail.listFromJson(entry.value, growable: growable,);
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

