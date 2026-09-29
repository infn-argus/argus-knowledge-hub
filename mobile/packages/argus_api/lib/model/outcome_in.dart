//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class OutcomeIn {
  /// Returns a new [OutcomeIn] instance.
  OutcomeIn({
    this.final_,
    required this.recordUid,
  });

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? final_;

  String recordUid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is OutcomeIn &&
    other.final_ == final_ &&
    other.recordUid == recordUid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (final_ == null ? 0 : final_!.hashCode) +
    (recordUid.hashCode);

  @override
  String toString() => 'OutcomeIn[final_=$final_, recordUid=$recordUid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.final_ != null) {
      json[r'final'] = this.final_;
    } else {
      json[r'final'] = null;
    }
      json[r'record_uid'] = this.recordUid;
    return json;
  }

  /// Returns a new [OutcomeIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static OutcomeIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "OutcomeIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "OutcomeIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return OutcomeIn(
        final_: mapValueOfType<Object>(json, r'final'),
        recordUid: mapValueOfType<String>(json, r'record_uid')!,
      );
    }
    return null;
  }

  static List<OutcomeIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OutcomeIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OutcomeIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, OutcomeIn> mapFromJson(dynamic json) {
    final map = <String, OutcomeIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = OutcomeIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of OutcomeIn-objects as value to a dart map
  static Map<String, List<OutcomeIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<OutcomeIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = OutcomeIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'record_uid',
  };
}

