//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class IssueCommentCreate {
  /// Returns a new [IssueCommentCreate] instance.
  IssueCommentCreate({
    required this.author,
    required this.body,
    required this.uid,
  });

  String author;

  String body;

  String uid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is IssueCommentCreate &&
    other.author == author &&
    other.body == body &&
    other.uid == uid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (author.hashCode) +
    (body.hashCode) +
    (uid.hashCode);

  @override
  String toString() => 'IssueCommentCreate[author=$author, body=$body, uid=$uid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'author'] = this.author;
      json[r'body'] = this.body;
      json[r'uid'] = this.uid;
    return json;
  }

  /// Returns a new [IssueCommentCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static IssueCommentCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "IssueCommentCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "IssueCommentCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return IssueCommentCreate(
        author: mapValueOfType<String>(json, r'author')!,
        body: mapValueOfType<String>(json, r'body')!,
        uid: mapValueOfType<String>(json, r'uid')!,
      );
    }
    return null;
  }

  static List<IssueCommentCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <IssueCommentCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = IssueCommentCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, IssueCommentCreate> mapFromJson(dynamic json) {
    final map = <String, IssueCommentCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = IssueCommentCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of IssueCommentCreate-objects as value to a dart map
  static Map<String, List<IssueCommentCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<IssueCommentCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = IssueCommentCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'author',
    'body',
    'uid',
  };
}

