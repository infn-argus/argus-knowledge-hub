//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AddressIn {
  /// Returns a new [AddressIn] instance.
  AddressIn({
    this.hostname,
    this.ip,
  });

  String? hostname;

  String? ip;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AddressIn &&
    other.hostname == hostname &&
    other.ip == ip;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (hostname == null ? 0 : hostname!.hashCode) +
    (ip == null ? 0 : ip!.hashCode);

  @override
  String toString() => 'AddressIn[hostname=$hostname, ip=$ip]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.hostname != null) {
      json[r'hostname'] = this.hostname;
    } else {
      json[r'hostname'] = null;
    }
    if (this.ip != null) {
      json[r'ip'] = this.ip;
    } else {
      json[r'ip'] = null;
    }
    return json;
  }

  /// Returns a new [AddressIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AddressIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AddressIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AddressIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AddressIn(
        hostname: mapValueOfType<String>(json, r'hostname'),
        ip: mapValueOfType<String>(json, r'ip'),
      );
    }
    return null;
  }

  static List<AddressIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AddressIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AddressIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AddressIn> mapFromJson(dynamic json) {
    final map = <String, AddressIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AddressIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AddressIn-objects as value to a dart map
  static Map<String, List<AddressIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AddressIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AddressIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}

