//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AskStep {
  /// Returns a new [AskStep] instance.
  AskStep({
    this.arguments,
    this.error,
    this.result = '',
    this.seconds = 0,
    required this.tool,
  });

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? arguments;

  String? error;

  String result;

  num seconds;

  String tool;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AskStep &&
    other.arguments == arguments &&
    other.error == error &&
    other.result == result &&
    other.seconds == seconds &&
    other.tool == tool;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (arguments == null ? 0 : arguments!.hashCode) +
    (error == null ? 0 : error!.hashCode) +
    (result.hashCode) +
    (seconds.hashCode) +
    (tool.hashCode);

  @override
  String toString() => 'AskStep[arguments=$arguments, error=$error, result=$result, seconds=$seconds, tool=$tool]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.arguments != null) {
      json[r'arguments'] = this.arguments;
    } else {
      json[r'arguments'] = null;
    }
    if (this.error != null) {
      json[r'error'] = this.error;
    } else {
      json[r'error'] = null;
    }
      json[r'result'] = this.result;
      json[r'seconds'] = this.seconds;
      json[r'tool'] = this.tool;
    return json;
  }

  /// Returns a new [AskStep] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AskStep? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AskStep[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AskStep[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AskStep(
        arguments: mapValueOfType<Object>(json, r'arguments'),
        error: mapValueOfType<String>(json, r'error'),
        result: mapValueOfType<String>(json, r'result') ?? '',
        seconds: num.parse('${json[r'seconds']}'),
        tool: mapValueOfType<String>(json, r'tool')!,
      );
    }
    return null;
  }

  static List<AskStep> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AskStep>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AskStep.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AskStep> mapFromJson(dynamic json) {
    final map = <String, AskStep>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AskStep.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AskStep-objects as value to a dart map
  static Map<String, List<AskStep>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AskStep>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AskStep.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'tool',
  };
}

