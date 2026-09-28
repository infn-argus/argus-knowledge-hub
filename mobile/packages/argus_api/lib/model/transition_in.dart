//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class TransitionIn {
  /// Returns a new [TransitionIn] instance.
  TransitionIn({
    this.assignee,
    this.comment,
    this.resolution,
    required this.to,
  });

  String? assignee;

  String? comment;

  String? resolution;

  String to;

  @override
  bool operator ==(Object other) => identical(this, other) || other is TransitionIn &&
    other.assignee == assignee &&
    other.comment == comment &&
    other.resolution == resolution &&
    other.to == to;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assignee == null ? 0 : assignee!.hashCode) +
    (comment == null ? 0 : comment!.hashCode) +
    (resolution == null ? 0 : resolution!.hashCode) +
    (to.hashCode);

  @override
  String toString() => 'TransitionIn[assignee=$assignee, comment=$comment, resolution=$resolution, to=$to]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.assignee != null) {
      json[r'assignee'] = this.assignee;
    } else {
      json[r'assignee'] = null;
    }
    if (this.comment != null) {
      json[r'comment'] = this.comment;
    } else {
      json[r'comment'] = null;
    }
    if (this.resolution != null) {
      json[r'resolution'] = this.resolution;
    } else {
      json[r'resolution'] = null;
    }
      json[r'to'] = this.to;
    return json;
  }

  /// Returns a new [TransitionIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static TransitionIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "TransitionIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "TransitionIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return TransitionIn(
        assignee: mapValueOfType<String>(json, r'assignee'),
        comment: mapValueOfType<String>(json, r'comment'),
        resolution: mapValueOfType<String>(json, r'resolution'),
        to: mapValueOfType<String>(json, r'to')!,
      );
    }
    return null;
  }

  static List<TransitionIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <TransitionIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = TransitionIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, TransitionIn> mapFromJson(dynamic json) {
    final map = <String, TransitionIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = TransitionIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of TransitionIn-objects as value to a dart map
  static Map<String, List<TransitionIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<TransitionIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = TransitionIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'to',
  };
}

